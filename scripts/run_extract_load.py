"""Extract from GitHub and load into the raw schema.

CLI:      python -m scripts.run_extract_load --lookback-days 1
Airflow:  imported by dags/github_pipeline_dag.py
"""
from __future__ import annotations

import argparse
import logging
from datetime import datetime, timedelta, timezone

import requests

from scripts.config import Settings, get_settings
from scripts.db_loader import WarehouseLoader
from scripts.github_extractor import GitHubClient, GitHubExtractor, RateLimitExceeded, parse_ts

log = logging.getLogger("run_extract_load")


def _to_dt(value: str | datetime) -> datetime:
    dt = value if isinstance(value, datetime) else parse_ts(value.replace(" ", "T", 1))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def check_api_health(settings: Settings | None = None) -> dict:
    """Fail fast when the token is missing, invalid, or the quota is nearly exhausted."""
    settings = settings or get_settings()
    if not settings.github_token:
        raise RuntimeError("GITHUB_TOKEN is not set; unauthenticated quota (60/hr) is too low")
    resources = GitHubClient(settings).health()
    core, search = resources["core"], resources["search"]
    log.info("core %s/%s remaining, search %s/%s remaining",
             core["remaining"], core["limit"], search["remaining"], search["limit"])
    if core["remaining"] < settings.min_rate_limit_remaining:
        raise RuntimeError(
            f"Only {core['remaining']} core requests left (need {settings.min_rate_limit_remaining}); "
            f"resets at epoch {core['reset']}"
        )
    return {"core_remaining": core["remaining"], "search_remaining": search["remaining"]}


def run_extract_load(
    since: str | datetime,
    until: str | datetime,
    languages: tuple[str, ...] | None = None,
    settings: Settings | None = None,
) -> dict:
    settings = settings or get_settings()
    since_dt, until_dt = _to_dt(since), _to_dt(until)
    languages = languages or settings.languages
    extractor = GitHubExtractor(GitHubClient(settings))
    stats = {"repos": 0, "events": 0, "failed_repos": []}

    with WarehouseLoader(settings) as loader:
        loader.ensure_schema()
        for language in languages:
            repos = extractor.fetch_top_repos(language)
            stats["repos"] += loader.upsert_repos(repos)
            for repo in repos:
                try:
                    events = extractor.collect_events(repo, since_dt, until_dt)
                    stats["events"] += loader.upsert_events(events)
                    log.info("%s: %d events", repo.full_name, len(events))
                except RateLimitExceeded:
                    raise
                except requests.RequestException as exc:
                    log.error("%s failed: %s", repo.full_name, exc)
                    stats["failed_repos"].append(repo.full_name)

    total = stats["repos"] or 1
    if len(stats["failed_repos"]) / total > 0.25:
        raise RuntimeError(f"Too many repo failures: {stats['failed_repos']}")
    log.info("Done: %s", stats)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since")
    parser.add_argument("--until")
    parser.add_argument("--lookback-days", type=int, default=1)
    parser.add_argument("--languages", help="comma-separated override")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    until = _to_dt(args.until) if args.until else datetime.now(timezone.utc)
    since = _to_dt(args.since) if args.since else until - timedelta(days=args.lookback_days)
    langs = tuple(args.languages.split(",")) if args.languages else None
    run_extract_load(since, until, langs)


if __name__ == "__main__":
    main()
