FROM apache/airflow:2.10.5-python3.12

ARG AIRFLOW_VERSION=2.10.5
ARG PYTHON_VERSION=3.12
ARG CONSTRAINT_URL=https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt

USER root
RUN mkdir -p /opt/dbt-venv && chown -R airflow:root /opt/dbt-venv

USER airflow
COPY --chown=airflow:root requirements.txt requirements-dbt.txt /tmp/

# Pipeline + Airflow dependencies (constrained to Airflow's tested versions)
RUN pip install --no-cache-dir -r /tmp/requirements.txt -c "${CONSTRAINT_URL}"

# dbt in its own virtualenv
RUN python -m venv /opt/dbt-venv \
 && /opt/dbt-venv/bin/pip install --no-cache-dir --upgrade pip \
 && /opt/dbt-venv/bin/pip install --no-cache-dir -r /tmp/requirements-dbt.txt

ENV PYTHONPATH=/opt/airflow \
    DBT_BIN=/opt/dbt-venv/bin/dbt \
    DBT_PROJECT_DIR=/opt/airflow/dbt \
    DBT_PROFILES_DIR=/opt/airflow/dbt

# Baked-in copies; docker-compose bind mounts override these for local development
COPY --chown=airflow:root dags/ /opt/airflow/dags/
COPY --chown=airflow:root scripts/ /opt/airflow/scripts/
COPY --chown=airflow:root dbt/ /opt/airflow/dbt/
