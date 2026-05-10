import json
import datetime
import os
import requests
from bs4 import BeautifulSoup
from minio import Minio
from io import BytesIO
import hashlib
from pathlib import Path


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

    print(f"[OK] Uploaded: {MINIO_BUCKET}/{object_name}")


def generate_hash(text: str):
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def scrape_medlineplus(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }

    response = requests.get(url, headers=headers, timeout=30)

    if response.status_code != 200:
        print(f"[ERROR] Failed request {response.status_code} -> {url}")
        return None

    soup = BeautifulSoup(response.text, "lxml")

    title = soup.find("h1")
    title_text = title.get_text(strip=True) if title else "No Title"

    content_div = soup.find("div", {"class": "main"})
    content_text = content_div.get_text(" ", strip=True) if content_div else "No Content"

    data = {
        "title": title_text,
        "content": content_text,
        "source": "MedlinePlus",
        "url": url,
        "scraped_at": datetime.datetime.now().isoformat()
    }

    return data


def read_urls(file_path: str):
    with open(file_path, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f.readlines() if line.strip()]
    return urls


def resolve_urls_file() -> str:
    """
    Keep backward compatibility with the original `urls.txt` name while
    supporting the file that actually exists in the repository.
    """
    candidates = [
        Path("scraping/urls.txt"),
        Path("scraping/urls_medline.txt"),
    ]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    raise FileNotFoundError("No scraping URL file found in scraping/")


if __name__ == "__main__":
    urls_file = resolve_urls_file()
    urls = read_urls(urls_file)

    print(f"[INFO] Found {len(urls)} URLs")

    for url in urls:
        print(f"\n[SCRAPING] {url}")
        article_data = scrape_medlineplus(url)

        if article_data:
            unique_id = generate_hash(url)
            filename = f"medline_{unique_id}.json"
            object_path = f"medical_articles/{filename}"

            upload_json_to_minio(object_path, article_data)

    print("\n[DONE] Batch scraping finished.")
