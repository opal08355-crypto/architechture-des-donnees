import json
import hashlib
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

URLS_FILE = "scraping/urls_nhs.txt"
OUTPUT_DIR = "scraping/output/bronze"


def ensure_output_dir() -> Path:
    path = Path(OUTPUT_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_urls(file_path: str) -> list[str]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"URLs file not found: {file_path}")

    with path.open("r", encoding="utf-8") as f:
        urls = [line.strip() for line in f.readlines() if line.strip()]

    return urls


def clean_text(text: str) -> str:
    return " ".join(text.split()).strip()


def extract_main_content(soup: BeautifulSoup) -> str:
    """
    NHS pages can vary a bit, so we try multiple selectors.
    """
    selectors = [
        "main",
        "article",
        '[role="main"]',
        ".nhsuk-width-container main",
        ".nhsuk-grid-row",
    ]

    for selector in selectors:
        content = soup.select_one(selector)
        if content:
            return clean_text(content.get_text(" ", strip=True))

    return ""


def scrape_nhs(url: str) -> dict | None:
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)

        if response.status_code != 200:
            print(f"[SKIPPED] {response.status_code} -> {url}")
            return None

        soup = BeautifulSoup(response.text, "lxml")

        title_tag = soup.find("h1")
        title = clean_text(title_tag.get_text()) if title_tag else "No Title"

        content = extract_main_content(soup)

        if not content:
            print(f"[SKIPPED] No content found -> {url}")
            return None

        data = {
            "title": title,
            "content": content,
            "source": "NHS",
            "url": url,
            "scraped_at": datetime.now().isoformat()
        }

        return data

    except requests.RequestException as e:
        print(f"[ERROR] Request failed -> {url} | {e}")
        return None
    except Exception as e:
        print(f"[ERROR] Unexpected error -> {url} | {e}")
        return None


def save_to_json(data: dict, output_dir: Path) -> None:
    url = data["url"]
    file_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
    file_path = output_dir / f"nhs_{file_hash}.json"

    with file_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print(f"[OK] Saved -> {file_path}")


def main():
    output_dir = ensure_output_dir()
    urls = load_urls(URLS_FILE)

    print(f"[INFO] Found {len(urls)} NHS URLs")

    for url in urls:
        print(f"[SCRAPING] {url}")
        data = scrape_nhs(url)
        if data:
            save_to_json(data, output_dir)

    print("[DONE] NHS scraping finished.")


if __name__ == "__main__":
    main()