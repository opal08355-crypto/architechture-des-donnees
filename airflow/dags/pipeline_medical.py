from __future__ import annotations

import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator


LOGGER = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[2]

POSTGRES_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "database": os.getenv("POSTGRES_DB", "medical_dw"),
    "user": os.getenv("POSTGRES_USER", "admin"),
    "password": os.getenv("POSTGRES_PASSWORD", "admin123"),
}


def run_project_script(script_relative_path: str) -> None:
    """
    Execute one repository script from the project root so relative paths
    inside the existing ETL scripts keep working unchanged.
    """
    script_path = REPO_ROOT / script_relative_path

    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")

    command = [sys.executable, str(script_path)]
    LOGGER.info("Running project script: %s", " ".join(command))

    completed = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    if completed.stdout:
        LOGGER.info(completed.stdout)
    if completed.stderr:
        LOGGER.warning(completed.stderr)

    if completed.returncode != 0:
        raise RuntimeError(
            f"Script failed with exit code {completed.returncode}: {script_relative_path}"
        )


def create_warehouse_tables() -> None:
    """
    Ensure PostgreSQL analytical tables exist before loading Gold data.
    """
    import psycopg2

    sql_path = REPO_ROOT / "warehouse" / "create_tables.sql"
    if not sql_path.exists():
        raise FileNotFoundError(f"Warehouse SQL file not found: {sql_path}")

    sql = sql_path.read_text(encoding="utf-8")

    LOGGER.info("Creating warehouse tables in PostgreSQL")
    connection = psycopg2.connect(**POSTGRES_CONFIG)
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(sql)
    finally:
        connection.close()


default_args = {
    "owner": "medical-bigdata-platform",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


with DAG(
    dag_id="pipeline_medical",
    description=(
        "Batch orchestration for the medical big data pipeline: "
        "scraping -> bronze -> silver -> gold -> warehouse"
    ),
    default_args=default_args,
    start_date=datetime(2026, 4, 1),
    schedule="0 * * * *",
    catchup=False,
    max_active_runs=1,
    tags=["medical", "etl", "airflow", "medallion"],
) as dag:
    scrape_batch_articles = PythonOperator(
        task_id="scrape_batch_articles",
        python_callable=run_project_script,
        op_kwargs={"script_relative_path": "scraping/scraper.py"},
    )

    transform_bronze_to_silver = PythonOperator(
        task_id="transform_bronze_to_silver",
        python_callable=run_project_script,
        op_kwargs={"script_relative_path": "spark/bronze_to_silver.py"},
    )

    enrich_silver_with_llm = PythonOperator(
        task_id="enrich_silver_with_llm",
        python_callable=run_project_script,
        op_kwargs={"script_relative_path": "spark/llm_enrich_silver.py"},
    )

    transform_silver_to_gold = PythonOperator(
        task_id="transform_silver_to_gold",
        python_callable=run_project_script,
        op_kwargs={"script_relative_path": "spark/silver_to_gold.py"},
    )

    create_postgres_tables = PythonOperator(
        task_id="create_postgres_tables",
        python_callable=create_warehouse_tables,
    )

    load_gold_to_postgres = PythonOperator(
        task_id="load_gold_to_postgres",
        python_callable=run_project_script,
        op_kwargs={"script_relative_path": "spark/load_gold_to_postgres.py"},
    )

    (
        scrape_batch_articles
        >> transform_bronze_to_silver
        >> enrich_silver_with_llm
        >> transform_silver_to_gold
        >> create_postgres_tables
        >> load_gold_to_postgres
    )
