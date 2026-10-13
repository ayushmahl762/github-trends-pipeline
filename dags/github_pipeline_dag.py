"""Daily GitHub trends pipeline: health check -> extract/load -> dbt run -> dbt test."""
from __future__ import annotations

import os
from datetime import timedelta

import pendulum
from airflow.decorators import dag
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

DBT_BIN = os.environ.get("DBT_BIN", "/opt/dbt-venv/bin/dbt")
DBT_FLAGS = (
    "--project-dir ${DBT_PROJECT_DIR:-/opt/airflow/dbt} "
    "--profiles-dir ${DBT_PROFILES_DIR:-/opt/airflow/dbt}"
)


def _check_api_health() -> dict:
    from scripts.run_extract_load import check_api_health

    return check_api_health()


def _extract_and_load(since: str, until: str) -> dict:
    from scripts.run_extract_load import run_extract_load

    return run_extract_load(since, until)


@dag(
    dag_id="github_trends_pipeline",
    description="GitHub REST API -> Postgres raw -> dbt staging/marts -> tests",
    schedule="@daily",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "data-engineering",
        "retries": 2,
        "retry_delay": timedelta(minutes=10),
        "retry_exponential_backoff": True,
    },
    tags=["github", "dbt", "postgres"],
)
def github_trends_pipeline():
    check_api = PythonOperator(
        task_id="check_github_api_health",
        python_callable=_check_api_health,
        execution_timeout=timedelta(minutes=2),
    )

    extract_load = PythonOperator(
        task_id="extract_and_load_raw",
        python_callable=_extract_and_load,
        op_kwargs={
            "since": "{{ data_interval_start.isoformat() }}",
            "until": "{{ data_interval_end.isoformat() }}",
        },
        execution_timeout=timedelta(hours=3),
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"{DBT_BIN} run {DBT_FLAGS}",
        execution_timeout=timedelta(minutes=30),
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"{DBT_BIN} test {DBT_FLAGS}",
        execution_timeout=timedelta(minutes=30),
    )

    check_api >> extract_load >> dbt_run >> dbt_test


github_trends_pipeline()
