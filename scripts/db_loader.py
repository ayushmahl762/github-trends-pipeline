"""PostgreSQL loader: raw schema DDL and idempotent upserts."""
from __future__ import annotations

import logging
from typing import Any, Iterable, Sequence

import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json, execute_values

from scripts.config import Settings
from scripts.models import EventRecord, RepoRecord

log = logging.getLogger(__name__)

DDL = """
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.raw_github_repos (
    repo_id            BIGINT PRIMARY KEY,
    full_name          TEXT        NOT NULL,
    name               TEXT        NOT NULL,
    owner_login        TEXT        NOT NULL,
    owner_type         TEXT        NOT NULL,
    description        TEXT,
    language           TEXT,
    stargazers_count   INTEGER     NOT NULL DEFAULT 0,
    forks_count        INTEGER     NOT NULL DEFAULT 0,
    open_issues_count  INTEGER     NOT NULL DEFAULT 0,
    watchers_count     INTEGER     NOT NULL DEFAULT 0,
    size_kb            INTEGER     NOT NULL DEFAULT 0,
    created_at         TIMESTAMPTZ NOT NULL,
    updated_at         TIMESTAMPTZ NOT NULL,
    pushed_at          TIMESTAMPTZ,
    license_spdx       TEXT,
    topics             JSONB       NOT NULL DEFAULT '[]'::jsonb,
    is_archived        BOOLEAN     NOT NULL DEFAULT FALSE,
    is_fork            BOOLEAN     NOT NULL DEFAULT FALSE,
    default_branch     TEXT,
    html_url           TEXT        NOT NULL,
    ingested_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.raw_github_events (
    event_id        TEXT PRIMARY KEY,
    repo_id         BIGINT      NOT NULL,
    repo_full_name  TEXT        NOT NULL,
    event_type      TEXT        NOT NULL,
    actor_login     TEXT,
    actor_id        BIGINT,
    org_login       TEXT,
    event_ts        TIMESTAMPTZ NOT NULL,
    payload         JSONB       NOT NULL DEFAULT '{}'::jsonb,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_raw_events_repo_ts ON raw.raw_github_events (repo_id, event_ts);
CREATE INDEX IF NOT EXISTS idx_raw_events_type_ts ON raw.raw_github_events (event_type, event_ts);
"""

REPO_COLUMNS = [
    "repo_id", "full_name", "name", "owner_login", "owner_type", "description", "language",
    "stargazers_count", "forks_count", "open_issues_count", "watchers_count", "size_kb",
    "created_at", "updated_at", "pushed_at", "license_spdx", "topics", "is_archived",
    "is_fork", "default_branch", "html_url",
]
EVENT_COLUMNS = [
    "event_id", "repo_id", "repo_full_name", "event_type", "actor_login", "actor_id",
    "org_login", "event_ts", "payload",
]
JSON_COLUMNS = {"topics", "payload"}


class WarehouseLoader:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.conn: Any = None

    def __enter__(self) -> "WarehouseLoader":
        self.conn = psycopg2.connect(self.settings.dsn)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type:
            self.conn.rollback()
        self.conn.close()

    def ensure_schema(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute(DDL)
        self.conn.commit()

    def _upsert(
        self,
        table: str,
        columns: Sequence[str],
        key: str,
        rows: Iterable[dict[str, Any]],
        page_size: int = 500,
    ) -> int:
        # Deduplicate on the key: ON CONFLICT cannot touch the same row twice in one statement.
        unique = {row[key]: row for row in rows}
        if not unique:
            return 0
        values = [
            tuple(Json(r[c]) if c in JSON_COLUMNS else r[c] for c in columns)
            for r in unique.values()
        ]
        updates = [
            sql.SQL("{c} = EXCLUDED.{c}").format(c=sql.Identifier(c)) for c in columns if c != key
        ]
        updates.append(sql.SQL("ingested_at = now()"))
        stmt = sql.SQL(
            "INSERT INTO raw.{table} ({cols}) VALUES %s ON CONFLICT ({key}) DO UPDATE SET {updates}"
        ).format(
            table=sql.Identifier(table),
            cols=sql.SQL(", ").join(map(sql.Identifier, columns)),
            key=sql.Identifier(key),
            updates=sql.SQL(", ").join(updates),
        )
        with self.conn.cursor() as cur:
            execute_values(cur, stmt, values, page_size=page_size)
        self.conn.commit()
        return len(values)

    def upsert_repos(self, repos: Iterable[RepoRecord]) -> int:
        return self._upsert(
            "raw_github_repos", REPO_COLUMNS, "repo_id", (r.model_dump() for r in repos)
        )

    def upsert_events(self, events: Iterable[EventRecord]) -> int:
        return self._upsert(
            "raw_github_events", EVENT_COLUMNS, "event_id", (e.model_dump() for e in events)
        )
