"""Pydantic models: validate API payloads before they reach the warehouse."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

EventType = Literal[
    "commit", "star", "issue_opened", "issue_closed", "pr_opened", "pr_closed", "pr_merged"
]


class RepoRecord(BaseModel):
    repo_id: int
    full_name: str
    name: str
    owner_login: str
    owner_type: str
    description: str | None = None
    language: str | None = None
    stargazers_count: int = 0
    forks_count: int = 0
    open_issues_count: int = 0
    watchers_count: int = 0
    size_kb: int = 0
    created_at: datetime
    updated_at: datetime
    pushed_at: datetime | None = None
    license_spdx: str | None = None
    topics: list[str] = Field(default_factory=list)
    is_archived: bool = False
    is_fork: bool = False
    default_branch: str | None = None
    html_url: str

    @classmethod
    def from_api(cls, item: dict[str, Any]) -> "RepoRecord":
        return cls(
            repo_id=item["id"],
            full_name=item["full_name"],
            name=item["name"],
            owner_login=item["owner"]["login"],
            owner_type=item["owner"]["type"],
            description=item.get("description"),
            language=item.get("language"),
            stargazers_count=item.get("stargazers_count") or 0,
            forks_count=item.get("forks_count") or 0,
            open_issues_count=item.get("open_issues_count") or 0,
            watchers_count=item.get("watchers_count") or 0,
            size_kb=item.get("size") or 0,
            created_at=item["created_at"],
            updated_at=item["updated_at"],
            pushed_at=item.get("pushed_at"),
            license_spdx=(item.get("license") or {}).get("spdx_id"),
            topics=item.get("topics") or [],
            is_archived=bool(item.get("archived")),
            is_fork=bool(item.get("fork")),
            default_branch=item.get("default_branch"),
            html_url=item["html_url"],
        )


class EventRecord(BaseModel):
    event_id: str
    repo_id: int
    repo_full_name: str
    event_type: EventType
    actor_login: str | None = None
    actor_id: int | None = None
    org_login: str | None = None
    event_ts: datetime
    payload: dict[str, Any] = Field(default_factory=dict)
