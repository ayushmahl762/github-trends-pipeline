import unittest
from datetime import datetime, timezone

from scripts.config import get_settings
from scripts.github_extractor import GitHubClient, GitHubExtractor, iso, parse_ts
from scripts.models import RepoRecord

REPO = RepoRecord.from_api({
    "id": 1, "full_name": "acme/widget", "name": "widget",
    "owner": {"login": "acme", "type": "Organization"},
    "language": "Python", "stargazers_count": 10,
    "created_at": "2020-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
    "html_url": "https://github.com/acme/widget",
})


class FakeClient:
    def __init__(self, items):
        self.items = items
        self.settings = get_settings()

    def paginate(self, *a, **k):
        yield from self.items


class RateLimitTests(unittest.TestCase):
    def test_retry_after_header_wins(self):
        self.assertEqual(GitHubClient.rate_limit_wait({"Retry-After": "30"}, "", 0), 31)

    def test_primary_limit_waits_until_reset(self):
        headers = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1100"}
        self.assertEqual(GitHubClient.rate_limit_wait(headers, "", 0, now=1000), 101)

    def test_secondary_limit_backs_off_exponentially(self):
        body = "You have exceeded a secondary rate limit"
        self.assertEqual(GitHubClient.rate_limit_wait({}, body, 0), 60)
        self.assertEqual(GitHubClient.rate_limit_wait({}, body, 2), 240)

    def test_plain_forbidden_is_not_a_rate_limit(self):
        self.assertIsNone(GitHubClient.rate_limit_wait({}, "Repository access blocked", 0))


class IssueEventTests(unittest.TestCase):
    def test_merged_pr_emits_open_and_merge_events(self):
        item = {
            "number": 7, "title": "Fix", "user": {"login": "dev", "id": 5},
            "created_at": "2026-10-04T01:00:00Z", "closed_at": "2026-10-04T05:00:00Z",
            "pull_request": {"merged_at": "2026-10-04T05:00:00Z"},
        }
        extractor = GitHubExtractor(FakeClient([item]))
        since = parse_ts("2026-10-04T00:00:00Z")
        until = parse_ts("2026-10-05T00:00:00Z")
        types = [e.event_type for e in extractor.issue_pr_events(REPO, since, until)]
        self.assertEqual(types, ["pr_opened", "pr_merged"])

    def test_events_outside_window_are_dropped(self):
        item = {"number": 8, "user": {"login": "dev", "id": 5},
                "created_at": "2026-09-01T00:00:00Z", "closed_at": None}
        extractor = GitHubExtractor(FakeClient([item]))
        since = datetime(2026, 10, 4, tzinfo=timezone.utc)
        until = datetime(2026, 10, 5, tzinfo=timezone.utc)
        self.assertEqual(list(extractor.issue_pr_events(REPO, since, until)), [])

    def test_org_login_set_only_for_organizations(self):
        item = {"number": 9, "user": {"login": "dev", "id": 5},
                "created_at": "2026-10-04T01:00:00Z", "closed_at": None}
        extractor = GitHubExtractor(FakeClient([item]))
        event = next(extractor.issue_pr_events(
            REPO, parse_ts("2026-10-04T00:00:00Z"), parse_ts("2026-10-05T00:00:00Z")))
        self.assertEqual(event.org_login, "acme")
        self.assertEqual(event.event_id, "issue_opened:1:9")


if __name__ == "__main__":
    unittest.main()
