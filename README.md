# GitHub Developer Trends Dashboard

Daily pipeline: GitHub REST API -> PostgreSQL `raw` -> dbt `staging` / `marts` -> Power BI.
Orchestrated by Apache Airflow (LocalExecutor) in Docker Compose.

```
GitHub API --(scripts/)--> raw.raw_github_repos / raw_github_events
                               |  dbt run
                               v
        staging.stg_repos / stg_events  -->  marts.dim_repositories, dim_languages,
                                             fact_repo_activity, fact_contributor_activity
                               |  dbt test
                               v
                          Power BI (localhost:5433)
```

## Quick start
```bash
cp .env.example .env     # set GITHUB_TOKEN, passwords, AIRFLOW_FERNET_KEY, AIRFLOW_SECRET_KEY
make up                  # builds the image, starts Postgres x2, Airflow
# Airflow UI: http://localhost:8080  (AIRFLOW_ADMIN_USER / AIRFLOW_ADMIN_PASSWORD)
make trigger             # run the DAG now (also runs daily at 00:00 UTC)
```
Generate the two keys:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
python -c "import secrets; print(secrets.token_hex(32))"
```

## Backfill
`python -m scripts.run_extract_load --since 2026-09-01T00:00:00Z --until 2026-10-01T00:00:00Z`
(inside the scheduler container). Stargazer and commit paging is capped by `MAX_PAGES_PER_ENDPOINT`.

## Design notes
- **Idempotent**: events are keyed by deterministic `event_id` (e.g. `commit:<repo>:<sha>`); re-runs upsert.
- **Rate limits**: primary limit sleeps to reset; secondary limit honours `Retry-After` or backs off; a wait
  longer than `MAX_RATE_LIMIT_WAIT` fails the task so Airflow retries. The health task fails fast if quota is low.
- **Request budget**: each repo costs about 3+ calls per run (commits, stargazers, issues/PRs). Defaults
  (8 languages x 25 repos) stay well inside the 5,000/hour authenticated quota. Raise `REPOS_PER_LANGUAGE` gradually.
- **Search API cap**: GitHub search returns at most 1,000 results per query and 30 requests/minute.
- **dbt isolation**: dbt lives in `/opt/dbt-venv` so it cannot conflict with Airflow's pinned dependencies.
- **Star history**: `raw_github_repos` keeps only the latest star count; daily star growth comes from `star` events.
- **Bots** (`*[bot]`) and unlinked commit identities are excluded from contributor rankings.

## Layout
`dags/` Airflow DAG · `scripts/` extractor and loader · `dbt/` models and tests ·
`analytics/` dashboard SQL and Power BI DAX · `powerbi/` Power BI reports and documentation ·
`sql/init/` warehouse schemas · `tests/` unit tests
