"""GitHub REST API extraction: repos, commits, stargazers, issue and PR activity.

Rate limiting:
  * primary limit   -> sleeps until X-RateLimit-Reset when remaining hits 0
  * secondary limit -> honours Retry-After, otherwise exponential backoff
  * 5xx / network   -> exponential backoff
  * 404/409/410/451 -> repo skipped (deleted, empty, DMCA) without failing the run
"""
from __future__ import annotations

import logging
import math
import time
from datetime import datetime, timezone
from typing import Any, Iterator, Mapping
from urllib.parse import parse_qs, urlparse

import requests
from pydantic import ValidationError

from scripts.config import Settings
from scripts.models import EventRecord, RepoRecord

log = logging.getLogger(__name__)

STAR_MEDIA_TYPE = "application/vnd.github.star+json"
NON_FATAL_STATUS = {404, 409, 410, 451}
RETRYABLE_STATUS = {500, 502, 503, 504}


class RateLimitExceeded(RuntimeError):
    """Raised when the required wait exceeds MAX_RATE_LIMIT_WAIT."""


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class GitHubClient:
    def __init__(self, settings: Settings, session: requests.Session | None = None):
        self.settings = settings
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "github-trends-pipeline",
            }
        )
        if settings.github_token:
            self.session.headers["Authorization"] = f"Bearer {settings.github_token}"

    # ------------------------------------------------------------------ rate limits
    @staticmethod
    def rate_limit_wait(
        headers: Mapping[str, str], body: str, attempt: int, now: float | None = None
    ) -> float | None:
        """Seconds to wait for a 403/429 response, or None if it is not a rate limit."""
        now = time.time() if now is None else now
        retry_after = headers.get("Retry-After", "")
        if retry_after.isdigit():  # secondary limit with explicit instruction
            return int(retry_after) + 1
        reset = headers.get("X-RateLimit-Reset", "")
        if headers.get("X-RateLimit-Remaining") == "0" and reset.isdigit():  # primary limit
            return max(int(reset) - now, 0) + 1
        text = body.lower()
        if "secondary rate limit" in text or "abuse detection" in text:
            return min(60 * 2**attempt, 900)
        if "rate limit" in text:
            return min(30 * 2**attempt, 600)
        return None

    def _sleep(self, seconds: float, reason: str) -> None:
        log.warning("Sleeping %.0fs (%s)", seconds, reason)
        time.sleep(seconds)

    def _throttle(self, resp: requests.Response) -> None:
        remaining = resp.headers.get("X-RateLimit-Remaining", "")
        reset = resp.headers.get("X-RateLimit-Reset", "")
        if remaining.isdigit() and reset.isdigit() and int(remaining) <= self.settings.rate_limit_buffer:
            wait = max(int(reset) - time.time(), 0) + 1
            if wait > self.settings.max_rate_limit_wait:
                raise RateLimitExceeded(f"rate limit resets in {wait:.0f}s")
            self._sleep(wait, f"{remaining} requests left in "
                              f"{resp.headers.get('X-RateLimit-Resource', 'core')} bucket")
        elif self.settings.request_delay:
            time.sleep(self.settings.request_delay)

    # ------------------------------------------------------------------ HTTP
    def request(
        self, url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None
    ) -> requests.Response:
        s = self.settings
        for attempt in range(s.max_retries + 1):
            try:
                resp = self.session.get(url, params=params, headers=headers, timeout=s.request_timeout)
            except (requests.ConnectionError, requests.Timeout) as exc:
                if attempt == s.max_retries:
                    raise
                self._sleep(min(2**attempt, 60), f"network error: {exc}")
                continue

            if resp.status_code == 200:
                self._throttle(resp)
                return resp
            if resp.status_code in NON_FATAL_STATUS:
                return resp
            if resp.status_code in (403, 429):
                wait = self.rate_limit_wait(resp.headers, resp.text, attempt)
                if wait is None:
                    resp.raise_for_status()  # genuine permission error (e.g. blocked repo)
                if wait > s.max_rate_limit_wait:
                    raise RateLimitExceeded(f"would need to wait {wait:.0f}s for {url}")
                self._sleep(wait, f"{resp.status_code} rate limit on {urlparse(url).path}")
                continue
            if resp.status_code in RETRYABLE_STATUS:
                self._sleep(min(2**attempt, 60), f"HTTP {resp.status_code}")
                continue
            resp.raise_for_status()
        raise RateLimitExceeded(f"retries exhausted for {url}")

    def paginate(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        max_pages: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Follow RFC 5988 Link headers; yields individual items."""
        next_url: str | None = url
        next_params = params
        pages = 0
        while next_url and (max_pages is None or pages < max_pages):
            resp = self.request(next_url, next_params, headers)
            if resp.status_code != 200:
                log.info("Skipping %s (HTTP %s)", next_url, resp.status_code)
                return
            data = resp.json()
            yield from (data["items"] if isinstance(data, dict) and "items" in data else data)
            pages += 1
            next_url = resp.links.get("next", {}).get("url")
            next_params = None  # the next URL already carries the query string

    def health(self) -> dict[str, Any]:
        resp = self.request(f"{self.settings.github_api_url}/rate_limit")
        return resp.json()["resources"]


class GitHubExtractor:
    def __init__(self, client: GitHubClient):
        self.client = client
        self.settings = client.settings

    # ------------------------------------------------------------------ repositories
    def fetch_top_repos(self, language: str) -> list[RepoRecord]:
        s = self.settings
        params = {
            "q": f'language:"{language}" stars:>={s.min_stars} fork:false archived:false',
            "sort": "stars",
            "order": "desc",
            "per_page": 100,
        }
        max_pages = math.ceil(s.repos_per_language / 100)
        repos: list[RepoRecord] = []
        for item in self.client.paginate(
            f"{s.github_api_url}/search/repositories", params, max_pages=max_pages
        ):
            try:
                repos.append(RepoRecord.from_api(item))
            except (ValidationError, KeyError) as exc:
                log.warning("Skipping malformed repo %s: %s", item.get("full_name"), exc)
            if len(repos) >= s.repos_per_language:
                break
        time.sleep(s.search_delay)
        log.info("Fetched %d %s repos", len(repos), language)
        return repos

    # ------------------------------------------------------------------ events
    @staticmethod
    def _make_event(
        repo: RepoRecord,
        event_id: str,
        event_type: str,
        ts: str,
        actor: dict[str, Any] | None,
        payload: dict[str, Any],
    ) -> EventRecord:
        return EventRecord(
            event_id=event_id,
            repo_id=repo.repo_id,
            repo_full_name=repo.full_name,
            event_type=event_type,
            actor_login=(actor or {}).get("login"),
            actor_id=(actor or {}).get("id"),
            org_login=repo.owner_login if repo.owner_type == "Organization" else None,
            event_ts=ts,
            payload=payload,
        )

    def commit_events(self, repo: RepoRecord, since: datetime, until: datetime) -> Iterator[EventRecord]:
        url = f"{self.settings.github_api_url}/repos/{repo.full_name}/commits"
        params = {"since": iso(since), "until": iso(until), "per_page": 100}
        for item in self.client.paginate(url, params, max_pages=self.settings.max_pages_per_endpoint):
            commit = item["commit"]
            message = (commit.get("message") or "").splitlines()
            yield self._make_event(
                repo,
                f"commit:{repo.repo_id}:{item['sha']}",
                "commit",
                commit["author"]["date"],
                item.get("author"),  # None when the commit email is not linked to an account
                {
                    "sha": item["sha"],
                    "author_name": commit["author"].get("name"),
                    "message": message[0][:200] if message else "",
                },
            )

    def star_events(self, repo: RepoRecord, since: datetime, until: datetime) -> Iterator[EventRecord]:
        """Stargazers come oldest-first with no date filter, so read pages from the end."""
        url = f"{self.settings.github_api_url}/repos/{repo.full_name}/stargazers"
        headers = {"Accept": STAR_MEDIA_TYPE}
        first = self.client.request(url, {"per_page": 100, "page": 1}, headers)
        if first.status_code != 200:
            return
        last = first.links.get("last", {}).get("url")
        last_page = int(parse_qs(urlparse(last).query)["page"][0]) if last else 1

        fetched = 0
        for page in range(last_page, 0, -1):
            if fetched >= self.settings.max_pages_per_endpoint:
                break
            resp = first if last_page == 1 else self.client.request(
                url, {"per_page": 100, "page": page}, headers
            )
            if resp.status_code != 200:
                break
            fetched += 1
            items = resp.json()
            for item in reversed(items):
                ts = parse_ts(item["starred_at"])
                if ts >= until:
                    continue
                if ts < since:
                    return
                user = item.get("user") or {}
                yield self._make_event(
                    repo, f"star:{repo.repo_id}:{user.get('id')}", "star",
                    item["starred_at"], user, {},
                )

    def issue_pr_events(self, repo: RepoRecord, since: datetime, until: datetime) -> Iterator[EventRecord]:
        """The issues endpoint returns issues and pull requests (marked by `pull_request`)."""
        url = f"{self.settings.github_api_url}/repos/{repo.full_name}/issues"
        params = {
            "state": "all", "since": iso(since), "sort": "updated",
            "direction": "desc", "per_page": 100,
        }
        for item in self.client.paginate(url, params, max_pages=self.settings.max_pages_per_endpoint):
            is_pr = "pull_request" in item
            number = item["number"]
            author = item.get("user")
            base = {"number": number, "title": (item.get("title") or "")[:200]}

            created = parse_ts(item["created_at"])
            if since <= created < until:
                kind = "pr_opened" if is_pr else "issue_opened"
                yield self._make_event(repo, f"{kind}:{repo.repo_id}:{number}", kind,
                                       item["created_at"], author, base)

            closed_at = item.get("closed_at")
            if closed_at and since <= parse_ts(closed_at) < until:
                if is_pr:
                    merged = bool((item.get("pull_request") or {}).get("merged_at"))
                    kind = "pr_merged" if merged else "pr_closed"
                else:
                    kind = "issue_closed"
                yield self._make_event(repo, f"{kind}:{repo.repo_id}:{number}", kind,
                                       closed_at, author, base)

    def collect_events(self, repo: RepoRecord, since: datetime, until: datetime) -> list[EventRecord]:
        events: list[EventRecord] = []
        for producer in (self.commit_events, self.star_events, self.issue_pr_events):
            try:
                for event in producer(repo, since, until):
                    events.append(event)
            except ValidationError as exc:
                log.warning("Invalid event for %s skipped: %s", repo.full_name, exc)
        return events
