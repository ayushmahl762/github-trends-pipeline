.PHONY: setup up down logs extract dbt-run dbt-test trigger test

setup:            ## create .env with generated secrets
	@test -f .env || cp .env.example .env
	@echo "Edit .env: set GITHUB_TOKEN, passwords, AIRFLOW_FERNET_KEY, AIRFLOW_SECRET_KEY"

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f airflow-scheduler

trigger:
	docker compose exec airflow-scheduler airflow dags trigger github_trends_pipeline

extract:          ## run extract+load manually for the last day
	docker compose exec airflow-scheduler python -m scripts.run_extract_load --lookback-days 1

dbt-run:
	docker compose exec airflow-scheduler bash -c '$$DBT_BIN run --project-dir $$DBT_PROJECT_DIR --profiles-dir $$DBT_PROFILES_DIR'

dbt-test:
	docker compose exec airflow-scheduler bash -c '$$DBT_BIN test --project-dir $$DBT_PROJECT_DIR --profiles-dir $$DBT_PROFILES_DIR'

test:
	python -m unittest discover -s tests -v
