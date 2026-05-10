import json
import datetime
import os
import requests
from bs4 import BeautifulSoup
from minio import Minio
from io import BytesIO


# =========================
# MinIO Configuration
# =========================
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "admin12345")
MINIO_BUCKET = os.getenv("MINIO_BRONZE_BUCKET", "bronze")


def upload_json_to_minio(object_name: str, data: dict):
    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False
    )

    if not client.bucket_exists(MINIO_BUCKET):
        client.make_bucket(MINIO_BUCKET)

    json_bytes = json.dumps(data, ensure_ascii=False, indent=4).encode("utf-8")
    json_stream = BytesIO(json_bytes)

    client.put_object(
        MINIO_BUCKET,
        object_name,
        json_stream,
        length=len(json_bytes),
        content_type="application/json"
    )

    print(f"[OK] Uploaded to MinIO: {MINIO_BUCKET}/{object_name}")


def scrape_medlineplus(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    response = requests.get(url, headers=headers, timeout=20)

    if response.status_code != 200:
        print(f"[ERROR] Failed request: {response.status_code}")
        return None

    soup = BeautifulSoup(response.text, "lxml")

    title = soup.find("h1")
    title_text = title.get_text(strip=True) if title else "No Title"

    content_div = soup.find("div", {"id": "topic-summary"})
    content_text = content_div.get_text(" ", strip=True) if content_div else "No Content"

    data = {
        "title": title_text,
        "content": content_text,
        "source": "MedlinePlus",
        "url": url,
        "scraped_at": datetime.datetime.now().isoformat()
    }

    return data


if __name__ == "__main__":
    url = "https://medlineplus.gov/diabetes.html"

    data = scrape_medlineplus(url)

    if data:
        filename = f"medline_diabetes_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        object_path = f"medical_articles/{filename}"

        upload_json_to_minio(object_path, data)
        print("[DONE] Scraping + Upload Finished")
