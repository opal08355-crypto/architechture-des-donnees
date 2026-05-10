import json
import os
from minio import Minio
import psycopg2

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "admin12345")
GOLD_BUCKET = os.getenv("MINIO_GOLD_BUCKET", "gold")

POSTGRES_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "database": os.getenv("POSTGRES_DB", "medical_dw"),
    "user": os.getenv("POSTGRES_USER", "admin"),
    "password": os.getenv("POSTGRES_PASSWORD", "admin123")
}


def get_minio_client():
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False
    )


def read_json_from_minio(client, object_name):
    response = client.get_object(GOLD_BUCKET, object_name)
    data = json.loads(response.read().decode("utf-8"))
    response.close()
    response.release_conn()
    return data


def insert_articles_by_source(cursor, data):
    cursor.execute("DELETE FROM articles_by_source")
    for source_name, article_count in data.items():
        cursor.execute(
            "INSERT INTO articles_by_source (source_name, article_count) VALUES (%s, %s)",
            (source_name, article_count)
        )


def insert_articles_by_category(cursor, data):
    cursor.execute("DELETE FROM articles_by_category")
    for category_name, article_count in data.items():
        cursor.execute(
            "INSERT INTO articles_by_category (category_name, article_count) VALUES (%s, %s)",
            (category_name, article_count)
        )


def insert_top_keywords(cursor, data):
    cursor.execute("DELETE FROM top_keywords")
    for keyword, frequency in data.items():
        cursor.execute(
            "INSERT INTO top_keywords (keyword, frequency) VALUES (%s, %s)",
            (keyword, frequency)
        )


def insert_global_stats(cursor, data):
    cursor.execute("DELETE FROM global_stats")
    cursor.execute(
        "INSERT INTO global_stats (total_articles, avg_content_length) VALUES (%s, %s)",
        (data.get("total_articles", 0), data.get("avg_content_length", 0))
    )


def main():
    minio_client = get_minio_client()

    articles_by_source = read_json_from_minio(minio_client, "analytics/articles_by_source.json")
    articles_by_category = read_json_from_minio(minio_client, "analytics/articles_by_category.json")
    top_keywords = read_json_from_minio(minio_client, "analytics/top_keywords.json")
    global_stats = read_json_from_minio(minio_client, "analytics/global_stats.json")

    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = conn.cursor()

    insert_articles_by_source(cursor, articles_by_source)
    insert_articles_by_category(cursor, articles_by_category)
    insert_top_keywords(cursor, top_keywords)
    insert_global_stats(cursor, global_stats)

    conn.commit()
    cursor.close()
    conn.close()

    print("[DONE] Gold data loaded into PostgreSQL successfully.")


if __name__ == "__main__":
    main()
