import json
import os
import re
from io import BytesIO
from minio import Minio
from bs4 import BeautifulSoup
from langdetect import detect, LangDetectException

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "admin12345")

BRONZE_BUCKET = os.getenv("MINIO_BRONZE_BUCKET", "bronze")
SILVER_BUCKET = os.getenv("MINIO_SILVER_BUCKET", "silver")

BRONZE_PREFIXES = [
    prefix.strip()
    for prefix in os.getenv(
        "BRONZE_PREFIXES",
        "medical_articles/,medical_articles_stream/",
    ).split(",")
    if prefix.strip()
]
SILVER_PREFIX = "medical_articles_clean/"


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


def clean_html(text):
    if not text:
        return ""
    soup = BeautifulSoup(text, "lxml")
    return soup.get_text(" ", strip=True)


def remove_medlineplus_noise(text: str) -> str:
    if not text:
        return ""

    patterns_to_remove = [
        r"On this page.*?Summary",
        r"Basics Summary Start Here Diagnosis and Tests Prevention and Risk Factors Treatments and Therapies",
        r"Learn More Living With Related Issues Specifics Genetics See, Play and Learn",
        r"Images Videos and Tutorials Test Your Knowledge Research Statistics and Research Journal Articles Resources",
        r"Find an Expert For You Children Women Older Adults Patient Handouts",
        r"Medical Encyclopedia.*",
        r"Related Health Topics.*",
        r"Genetics.*",
        r"Journal Articles.*",
        r"References.*",
        r"Article:.*",
        r"Also in Spanish",
        r"\(Centers for Disease Control and Prevention\)",
        r"\(American Academy of Allergy, Asthma, and Immunology\)",
        r"\(American Lung Association\)",
        r"\(Mayo Foundation for Medical Education and Research\)",
        r"\(American Thoracic Society\)",
        r"- PDF",
    ]

    cleaned = text
    for pattern in patterns_to_remove:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

    return cleaned


def normalize_text(text):
    if not text:
        return ""

    text = remove_medlineplus_noise(text)
    text = re.sub(r"[^\w\s.,;:!?()/\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def detect_language(text):
    try:
        if not text or len(text) < 20:
            return "unknown"
        return detect(text)
    except LangDetectException:
        return "unknown"


def extract_category(url, title):
    url = (url or "").lower()
    title = (title or "").lower()

    if "diabetes" in url or "diabetes" in title:
        return "disease"
    if "asthma" in url or "asthma" in title:
        return "disease"
    if "flu" in url or "influenza" in url or "flu" in title:
        return "disease"
    if "pressure" in url or "hypertension" in url or "blood pressure" in title:
        return "disease"
    if "covid" in url or "coronavirus" in url or "covid" in title:
        return "disease"
    return "medical_info"


def is_valid_record(data):
    title = data.get("title", "").strip()
    content = data.get("content", "").strip()
    url = data.get("url", "").strip()

    if not title:
        return False, "Missing title"
    if not content:
        return False, "Missing content"
    if len(content) < 50:
        return False, "Content too short"
    if not url:
        return False, "Missing URL"

    return True, "Valid"


def transform_record(raw_data):
    raw_title = raw_data.get("title", "")
    raw_content = raw_data.get("content", "")

    clean_title = normalize_text(clean_html(raw_title))
    clean_content = normalize_text(clean_html(raw_content))
    language = detect_language(clean_content)
    category = extract_category(raw_data.get("url", ""), clean_title)

    silver_data = {
        "title": clean_title,
        "content": clean_content,
        "source": raw_data.get("source", ""),
        "url": raw_data.get("url", ""),
        "scraped_at": raw_data.get("scraped_at", ""),
        "language": language,
        "category": category,
        "content_length": len(clean_content)
    }

    return silver_data


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


def list_bronze_objects(client):
    seen = set()
    for prefix in BRONZE_PREFIXES:
        for obj in client.list_objects(BRONZE_BUCKET, prefix=prefix, recursive=True):
            if obj.object_name in seen:
                continue
            seen.add(obj.object_name)
            yield obj


def process_bronze_to_silver():
    client = get_minio_client()
    ensure_bucket_exists(client, SILVER_BUCKET)

    found = False

    for obj in list_bronze_objects(client):
        found = True
        print(f"\n[READING] {obj.object_name}")

        response = client.get_object(BRONZE_BUCKET, obj.object_name)
        raw_content = response.read().decode("utf-8")
        response.close()
        response.release_conn()

        try:
            raw_data = json.loads(raw_content)
        except json.JSONDecodeError:
            print("[ERROR] Invalid JSON, skipped")
            continue

        silver_data = transform_record(raw_data)
        valid, reason = is_valid_record(silver_data)

        if not valid:
            print(f"[SKIPPED] {reason}")
            continue

        filename = obj.object_name.split("/")[-1]
        silver_object_name = f"{SILVER_PREFIX}{filename}"

        upload_json(client, SILVER_BUCKET, silver_object_name, silver_data)

    if not found:
        print("[WARNING] No bronze files found")


if __name__ == "__main__":
    process_bronze_to_silver()
    print("\n[DONE] Bronze -> Silver transformation completed.")
