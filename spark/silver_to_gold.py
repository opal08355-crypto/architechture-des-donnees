import json
import os
import re
from io import BytesIO
from collections import Counter
from minio import Minio

# =========================
# MinIO Configuration
# =========================
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "admin12345")

SILVER_BUCKET = os.getenv("MINIO_SILVER_BUCKET", "silver")
GOLD_BUCKET = os.getenv("MINIO_GOLD_BUCKET", "gold")

SILVER_PREFIX = "medical_articles_clean/"
GOLD_PREFIX = "analytics/"


STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "are", "was", "were",
    "have", "has", "had", "you", "your", "about", "into", "they", "them",
    "their", "will", "would", "there", "what", "when", "where", "which",
    "how", "why", "can", "could", "should", "may", "might", "than", "then",
    "also", "more", "most", "some", "such", "any", "all", "not", "but", "too",
    "very", "is", "a", "an", "of", "to", "in", "on", "at", "by", "or", "as",
    "it", "be", "if", "do", "does", "did", "we", "our", "us"
}


def get_minio_client():
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False
    )


def ensure_bucket_exists(client, bucket_name):
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)
        print(f"[INFO] Bucket created: {bucket_name}")


def upload_json(client, bucket_name, object_name, data):
    json_bytes = json.dumps(data, ensure_ascii=False, indent=4).encode("utf-8")
    json_stream = BytesIO(json_bytes)

    client.put_object(
        bucket_name,
        object_name,
        json_stream,
        length=len(json_bytes),
        content_type="application/json"
    )

    print(f"[OK] Uploaded: {bucket_name}/{object_name}")


def tokenize(text):
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    return [w for w in words if w not in STOPWORDS]


def process_silver_to_gold():
    client = get_minio_client()
    ensure_bucket_exists(client, GOLD_BUCKET)

    objects = client.list_objects(SILVER_BUCKET, prefix=SILVER_PREFIX, recursive=True)

    source_counter = Counter()
    category_counter = Counter()
    word_counter = Counter()
    total_articles = 0
    total_content_length = 0

    found = False

    for obj in objects:
        found = True
        print(f"[READING] {obj.object_name}")

        response = client.get_object(SILVER_BUCKET, obj.object_name)
        raw_content = response.read().decode("utf-8")
        response.close()
        response.release_conn()

        try:
            data = json.loads(raw_content)
        except json.JSONDecodeError:
            print("[ERROR] Invalid JSON, skipped")
            continue

        total_articles += 1
        source_counter[data.get("source", "unknown")] += 1
        category_counter[data.get("category", "unknown")] += 1
        total_content_length += data.get("content_length", 0)

        content = data.get("content", "")
        word_counter.update(tokenize(content))

    if not found:
        print("[WARNING] No silver files found")
        return

    avg_content_length = total_content_length / total_articles if total_articles > 0 else 0

    articles_by_source = dict(source_counter)
    articles_by_category = dict(category_counter)
    top_keywords = dict(word_counter.most_common(20))

    global_stats = {
        "total_articles": total_articles,
        "avg_content_length": avg_content_length
    }

    upload_json(client, GOLD_BUCKET, f"{GOLD_PREFIX}articles_by_source.json", articles_by_source)
    upload_json(client, GOLD_BUCKET, f"{GOLD_PREFIX}articles_by_category.json", articles_by_category)
    upload_json(client, GOLD_BUCKET, f"{GOLD_PREFIX}top_keywords.json", top_keywords)
    upload_json(client, GOLD_BUCKET, f"{GOLD_PREFIX}global_stats.json", global_stats)


if __name__ == "__main__":
    process_silver_to_gold()
    print("\n[DONE] Silver -> Gold transformation completed.")
