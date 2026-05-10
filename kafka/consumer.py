import json
import hashlib
import os
from kafka import KafkaConsumer
from minio import Minio
from io import BytesIO


KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "medical_articles")
KAFKA_SERVER = os.getenv("KAFKA_SERVER", "localhost:9092")

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "admin12345")
MINIO_BUCKET = os.getenv("MINIO_BRONZE_BUCKET", "bronze")


def upload_to_minio(data: dict):
    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False
    )

    if not client.bucket_exists(MINIO_BUCKET):
        client.make_bucket(MINIO_BUCKET)

    url = data.get("url", "unknown")
    unique_id = hashlib.md5(url.encode("utf-8")).hexdigest()

    filename = f"stream_{unique_id}.json"
    object_path = f"medical_articles_stream/{filename}"

    json_bytes = json.dumps(data, ensure_ascii=False, indent=4).encode("utf-8")
    json_stream = BytesIO(json_bytes)

    client.put_object(
        MINIO_BUCKET,
        object_path,
        json_stream,
        length=len(json_bytes),
        content_type="application/json"
    )

    print(f"[OK] Saved in MinIO: {MINIO_BUCKET}/{object_path}")


if __name__ == "__main__":
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_SERVER,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id="medical-group"
    )

    print("[INFO] Consumer started... waiting for messages")

    for message in consumer:
        data = message.value
        print(f"\n[RECEIVED] {data.get('title')}")
        upload_to_minio(data)
