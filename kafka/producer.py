import json
import datetime
import os
import requests
from bs4 import BeautifulSoup
from kafka import KafkaProducer


KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "medical_articles")
KAFKA_SERVER = os.getenv("KAFKA_SERVER", "localhost:9092")


def scrape_medlineplus(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }

    response = requests.get(url, headers=headers, timeout=30)

    if response.status_code != 200:
        print(f"[ERROR] {response.status_code} -> {url}")
        return None

    soup = BeautifulSoup(response.text, "lxml")

    title = soup.find("h1")
    title_text = title.get_text(strip=True) if title else "No Title"

    content_div = soup.find("div", {"class": "main"})
    content_text = content_div.get_text(" ", strip=True) if content_div else "No Content"

    return {
        "title": title_text,
        "content": content_text,
        "source": "MedlinePlus",
        "url": url,
        "scraped_at": datetime.datetime.now().isoformat()
    }


def send_to_kafka(data: dict):
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_SERVER,
        value_serializer=lambda v: json.dumps(v).encode("utf-8")
    )

    producer.send(KAFKA_TOPIC, data)
    producer.flush()
    print("[OK] Sent to Kafka")


if __name__ == "__main__":
    urls = [
        "https://medlineplus.gov/diabetes.html",
        "https://medlineplus.gov/asthma.html",
        "https://medlineplus.gov/highbloodpressure.html",
        "https://medlineplus.gov/flu.html"
    ]

    for url in urls:
        print(f"\n[SCRAPING] {url}")
        data = scrape_medlineplus(url)

        if data:
            send_to_kafka(data)

    print("\n[DONE] Producer finished.")
