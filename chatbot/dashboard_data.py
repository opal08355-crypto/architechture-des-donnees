import json
import os
from datetime import datetime, timezone

import psycopg2
from minio import Minio

from chatbot.learning_store import learning_summary
from chatbot.metrics_store import read_chatbot_metrics

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "admin12345")
MINIO_GOLD_BUCKET = os.getenv("MINIO_GOLD_BUCKET", "gold")

POSTGRES_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "database": os.getenv("POSTGRES_DB", "medical_dw"),
    "user": os.getenv("POSTGRES_USER", "admin"),
    "password": os.getenv("POSTGRES_PASSWORD", "admin123"),
    "connect_timeout": 3,
}


def utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_counts(mapping: dict) -> list[dict]:
    rows = []
    for label, value in (mapping or {}).items():
        rows.append({"label": str(label), "value": int(value or 0)})
    rows.sort(key=lambda item: item["value"], reverse=True)
    return rows


def normalize_keywords(mapping: dict) -> list[dict]:
    rows = []
    for label, value in (mapping or {}).items():
        rows.append({"label": str(label), "value": int(value or 0)})
    rows.sort(key=lambda item: item["value"], reverse=True)
    return rows[:20]


def build_payload(
    *,
    source_kind: str,
    articles_by_source: dict | None = None,
    articles_by_category: dict | None = None,
    top_keywords: dict | None = None,
    global_stats: dict | None = None,
    chatbot_metrics: dict | None = None,
    learning_metrics: dict | None = None,
    warnings: list[str] | None = None,
) -> dict:
    source_rows = normalize_counts(articles_by_source or {})
    category_rows = normalize_counts(articles_by_category or {})
    keyword_rows = normalize_keywords(top_keywords or {})
    global_stats = global_stats or {}

    total_articles = int(global_stats.get("total_articles", 0) or 0)
    avg_content_length = float(global_stats.get("avg_content_length", 0) or 0)
    chatbot_metrics = chatbot_metrics or {}
    learning_metrics = learning_metrics or {}

    return {
        "status": "ok",
        "source_kind": source_kind,
        "generated_at": utc_iso_now(),
        "warnings": warnings or [],
        "kpis": {
            "total_articles": total_articles,
            "avg_content_length": round(avg_content_length, 1),
            "source_count": len(source_rows),
            "category_count": len(category_rows),
            "chat_questions": int(chatbot_metrics.get("total_questions", 0) or 0),
            "chat_avg_latency_ms": float(chatbot_metrics.get("avg_latency_ms", 0) or 0),
            "feedback_items": int(learning_metrics.get("feedback_items", 0) or 0),
        },
        "articles_by_source": source_rows,
        "articles_by_category": category_rows,
        "top_keywords": keyword_rows,
        "global_stats": {
            "total_articles": total_articles,
            "avg_content_length": round(avg_content_length, 1),
        },
        "chatbot_metrics": chatbot_metrics,
        "learning_metrics": learning_metrics,
    }


def fetch_dashboard_from_postgres() -> dict:
    connection = psycopg2.connect(**POSTGRES_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT source_name, article_count FROM articles_by_source")
            articles_by_source = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute("SELECT category_name, article_count FROM articles_by_category")
            articles_by_category = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute("SELECT keyword, frequency FROM top_keywords")
            top_keywords = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute(
                "SELECT total_articles, avg_content_length FROM global_stats ORDER BY id DESC LIMIT 1"
            )
            stats_row = cursor.fetchone() or (0, 0)
            global_stats = {
                "total_articles": stats_row[0] or 0,
                "avg_content_length": stats_row[1] or 0,
            }
    finally:
        connection.close()

    return build_payload(
        source_kind="postgres",
        articles_by_source=articles_by_source,
        articles_by_category=articles_by_category,
        top_keywords=top_keywords,
        global_stats=global_stats,
        chatbot_metrics=read_chatbot_metrics(),
        learning_metrics=learning_summary(),
    )


def get_minio_client():
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )


def read_json_from_minio(client: Minio, object_name: str):
    response = client.get_object(MINIO_GOLD_BUCKET, object_name)
    try:
        return json.loads(response.read().decode("utf-8"))
    finally:
        response.close()
        response.release_conn()


def fetch_dashboard_from_minio() -> dict:
    client = get_minio_client()
    articles_by_source = read_json_from_minio(client, "analytics/articles_by_source.json")
    articles_by_category = read_json_from_minio(client, "analytics/articles_by_category.json")
    top_keywords = read_json_from_minio(client, "analytics/top_keywords.json")
    global_stats = read_json_from_minio(client, "analytics/global_stats.json")

    return build_payload(
        source_kind="minio_fallback",
        articles_by_source=articles_by_source,
        articles_by_category=articles_by_category,
        top_keywords=top_keywords,
        global_stats=global_stats,
        chatbot_metrics=read_chatbot_metrics(),
        learning_metrics=learning_summary(),
        warnings=["PostgreSQL unavailable, dashboard loaded from Gold files in MinIO."],
    )


def fetch_dashboard_data() -> dict:
    errors = []

    try:
        return fetch_dashboard_from_postgres()
    except Exception as exc:
        errors.append(f"postgres: {exc}")

    try:
        payload = fetch_dashboard_from_minio()
        payload["warnings"].extend(errors)
        return payload
    except Exception as exc:
        errors.append(f"minio: {exc}")

    return build_payload(
        source_kind="empty",
        chatbot_metrics=read_chatbot_metrics(),
        learning_metrics=learning_summary(),
        warnings=errors or ["No analytics data source is currently available."],
    )
