"""Central configuration, read from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _csv(name: str, default: str) -> tuple[str, ...]:
    return tuple(v.strip() for v in os.environ.get(name, default).split(",") if v.strip())


@dataclass(frozen=True)
class Settings:
    github_token: str
    github_api_url: str
    languages: tuple[str, ...]
    repos_per_language: int
    min_stars: int
    max_pages_per_endpoint: int
    request_timeout: int
    max_retries: int
    max_rate_limit_wait: int
    min_rate_limit_remaining: int
    rate_limit_buffer: int
    request_delay: float
    search_delay: float
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str

    @property
    def dsn(self) -> str:
        return (
            f"host={self.db_host} port={self.db_port} dbname={self.db_name} "
            f"user={self.db_user} password={self.db_password}"
        )


def get_settings() -> Settings:
    env = os.environ
    return Settings(
        github_token=env.get("GITHUB_TOKEN", ""),
        github_api_url=env.get("GITHUB_API_URL", "https://api.github.com").rstrip("/"),
        languages=_csv("GITHUB_LANGUAGES", "Python,JavaScript,TypeScript,Rust,Go,Java,C++,C#"),
        repos_per_language=int(env.get("REPOS_PER_LANGUAGE", "25")),
        min_stars=int(env.get("MIN_STARS", "1000")),
        max_pages_per_endpoint=int(env.get("MAX_PAGES_PER_ENDPOINT", "5")),
        request_timeout=int(env.get("REQUEST_TIMEOUT", "30")),
        max_retries=int(env.get("MAX_RETRIES", "5")),
        max_rate_limit_wait=int(env.get("MAX_RATE_LIMIT_WAIT", "3900")),
        min_rate_limit_remaining=int(env.get("MIN_RATE_LIMIT_REMAINING", "300")),
        rate_limit_buffer=int(env.get("RATE_LIMIT_BUFFER", "5")),
        request_delay=float(env.get("REQUEST_DELAY", "0.1")),
        search_delay=float(env.get("SEARCH_DELAY", "2.5")),  # search API: 30 req/min
        db_host=env.get("WAREHOUSE_HOST", "localhost"),
        db_port=int(env.get("WAREHOUSE_PORT", "5432")),
        db_name=env.get("WAREHOUSE_DB", "github_trends"),
        db_user=env.get("WAREHOUSE_USER", "warehouse"),
        db_password=env.get("WAREHOUSE_PASSWORD", ""),
    )
