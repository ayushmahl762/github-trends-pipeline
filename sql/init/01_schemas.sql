-- Runs once, when the warehouse volume is first created.
CREATE SCHEMA IF NOT EXISTS raw;       -- loaded by scripts/db_loader.py
CREATE SCHEMA IF NOT EXISTS staging;   -- dbt views
CREATE SCHEMA IF NOT EXISTS marts;     -- dbt tables consumed by BI
