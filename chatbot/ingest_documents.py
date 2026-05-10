import json
import os
import re

import chromadb
from chromadb.utils import embedding_functions
from minio import Minio


MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "admin12345")

SILVER_BUCKET = os.getenv("MINIO_SILVER_BUCKET", "silver")
SILVER_PREFIX = os.getenv("SILVER_PREFIX", "medical_articles_clean/")
GOLD_BUCKET = os.getenv("MINIO_GOLD_BUCKET", "gold")
LLM_GOLD_PREFIX = os.getenv("LLM_GOLD_PREFIX", "llm_enriched/")

CHROMA_DB_PATH = "chatbot/chroma_db"
COLLECTION_NAME = "medical_chunks"
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")


DISEASE_KEYWORDS = {
    "covid": ["covid", "covid-19", "coronavirus", "sars-cov-2"],
    "asthma": ["asthma"],
    "diabetes": ["diabetes", "blood sugar", "glucose"],
    "flu": ["flu", "influenza"],
    "heart": ["heart disease", "heart diseases", "cardiac"],
    "stroke": ["stroke"],
    "obesity": ["obesity", "overweight"],
    "pneumonia": ["pneumonia"],
    "arthritis": ["arthritis"],
    "kidney": ["kidney", "renal"],
    "lung_cancer": ["lung cancer"],
    "lung": ["lung disease", "lung diseases"],
    "bloodpressure": ["blood pressure", "high blood pressure", "hypertension"],
}

ENRICHED_SECTION_MAP = {
    "summary": "definition",
    "key_symptoms": "symptoms",
    "causes": "causes",
    "treatments": "treatment",
    "medications": "treatment",
    "red_flags": "general",
    "contraindications": "general",
    "preventive_tips": "prevention",
}


def get_minio_client():
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", str(text))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def detect_disease(title: str, content: str) -> str:
    searchable = f"{title} {content}".lower()
    for disease, keywords in DISEASE_KEYWORDS.items():
        if any(keyword in searchable for keyword in keywords):
            return disease
    return ""


def detect_section(text: str) -> str:
    s = text.lower()
    symptoms_keywords = [
        "symptom", "symptoms", "wheezing", "cough", "shortness of breath",
        "chest tightness", "fever", "fatigue", "pain", "sore throat",
    ]
    causes_keywords = [
        "cause", "causes", "caused by", "virus", "infection",
        "spread", "trigger", "risk factor", "sars-cov-2", "coronavirus",
    ]
    prevention_keywords = [
        "prevent", "prevention", "avoid", "protect", "mask",
        "wash", "vaccination", "vaccine", "reduce risk",
    ]
    treatment_keywords = [
        "treatment", "treat", "therapy", "medicine",
        "medication", "drug", "care", "managed", "control",
    ]
    definition_keywords = [
        "is a", "is an", "is the", "refers to", "defined as", "chronic",
    ]

    if any(keyword in s for keyword in symptoms_keywords):
        return "symptoms"
    if any(keyword in s for keyword in causes_keywords):
        return "causes"
    if any(keyword in s for keyword in prevention_keywords):
        return "prevention"
    if any(keyword in s for keyword in treatment_keywords):
        return "treatment"
    if any(keyword in s for keyword in definition_keywords):
        return "definition"
    return "general"


def chunk_text_by_words(text: str, chunk_size: int = 120, overlap: int = 30):
    words = clean_text(text).split()
    if not words:
        return []

    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk_words = words[start:end]
        chunk_text = " ".join(chunk_words).strip()
        if chunk_text:
            chunks.append(chunk_text)
        if end >= len(words):
            break
        start += max(chunk_size - overlap, 1)
    return chunks


def is_noisy_chunk(text: str) -> bool:
    if not text:
        return True
    normalized = clean_text(text).lower()
    noise_patterns = [
        "start here diagnosis and tests prevention and risk factors treatments and therapies",
        "learn more related issues specifics",
        "images videos and tutorials test your knowledge",
        "find an expert for you",
    ]
    if any(pattern in normalized for pattern in noise_patterns):
        return True
    if len(normalized.split()) < 10:
        return True
    return False


def read_json_object(client: Minio, bucket_name: str, object_name: str):
    response = client.get_object(bucket_name, object_name)
    try:
        return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    finally:
        response.close()
        response.release_conn()


def as_text_list(value) -> list[str]:
    if isinstance(value, list):
        return [clean_text(item) for item in value if clean_text(item)]
    if isinstance(value, str):
        item = clean_text(value)
        return [item] if item else []
    return []


def build_stored_text(
    *,
    title: str,
    category: str,
    section: str,
    source: str,
    content: str,
    url: str,
) -> str:
    return (
        f"Title: {title}\n"
        f"Category: {category}\n"
        f"Section: {section}\n"
        f"Source: {source}\n"
        f"Content: {content}\n"
        f"URL: {url}"
    )


def read_llm_enriched_documents():
    client = get_minio_client()
    objects = client.list_objects(GOLD_BUCKET, prefix=LLM_GOLD_PREFIX, recursive=True)
    all_chunks = []

    for obj in objects:
        print(f"[READING][ENRICHED] {obj.object_name}")
        data = read_json_object(client, GOLD_BUCKET, obj.object_name)
        if not isinstance(data, dict):
            continue

        title = clean_text(data.get("title", ""))
        content = clean_text(data.get("content", ""))
        category = clean_text(data.get("category", ""))
        source = clean_text(data.get("source", ""))
        url = clean_text(data.get("url", ""))

        enrichment = data.get("llm_enrichment", {}) if isinstance(data.get("llm_enrichment"), dict) else {}
        llm_method = clean_text(data.get("llm_method", ""))
        llm_model = clean_text(data.get("llm_model", ""))
        llm_confidence = clean_text(enrichment.get("confidence", ""))
        disease_hint = clean_text(enrichment.get("disease", ""))
        disease = detect_disease(disease_hint or title, content)

        base_id = obj.object_name.replace("/", "_")

        for enrichment_key, section_name in ENRICHED_SECTION_MAP.items():
            values = as_text_list(enrichment.get(enrichment_key))
            if not values:
                continue

            merged_text = " ".join(values)
            for index, chunk_text in enumerate(chunk_text_by_words(merged_text, chunk_size=110, overlap=25)):
                if is_noisy_chunk(chunk_text):
                    continue

                stored_text = build_stored_text(
                    title=title,
                    category=category,
                    section=section_name,
                    source=source,
                    content=chunk_text,
                    url=url,
                )
                all_chunks.append(
                    {
                        "id": f"{base_id}_enriched_{enrichment_key}_{index}",
                        "text": stored_text,
                        "metadata": {
                            "title": title,
                            "category": category,
                            "section": section_name,
                            "source": source,
                            "url": url,
                            "chunk_index": index,
                            "disease": disease,
                            "enriched": "true",
                            "llm_method": llm_method,
                            "llm_model": llm_model,
                            "llm_confidence": llm_confidence,
                        },
                    }
                )

        if content:
            for index, chunk_text in enumerate(chunk_text_by_words(content, chunk_size=140, overlap=35)):
                if is_noisy_chunk(chunk_text):
                    continue
                section_name = detect_section(chunk_text)
                stored_text = build_stored_text(
                    title=title,
                    category=category,
                    section=section_name,
                    source=source,
                    content=chunk_text,
                    url=url,
                )
                all_chunks.append(
                    {
                        "id": f"{base_id}_base_{index}",
                        "text": stored_text,
                        "metadata": {
                            "title": title,
                            "category": category,
                            "section": section_name,
                            "source": source,
                            "url": url,
                            "chunk_index": index,
                            "disease": disease,
                            "enriched": "true",
                            "llm_method": llm_method,
                            "llm_model": llm_model,
                            "llm_confidence": llm_confidence,
                        },
                    }
                )

    return all_chunks


def read_silver_documents():
    client = get_minio_client()
    objects = client.list_objects(SILVER_BUCKET, prefix=SILVER_PREFIX, recursive=True)
    all_chunks = []

    for obj in objects:
        print(f"[READING][SILVER] {obj.object_name}")
        data = read_json_object(client, SILVER_BUCKET, obj.object_name)
        if not isinstance(data, dict):
            continue

        title = clean_text(data.get("title", ""))
        content = clean_text(data.get("content", ""))
        category = clean_text(data.get("category", ""))
        source = clean_text(data.get("source", ""))
        url = clean_text(data.get("url", ""))
        disease = detect_disease(title, content)

        if not content:
            continue

        base_id = obj.object_name.replace("/", "_")
        for index, chunk_text in enumerate(chunk_text_by_words(content, chunk_size=120, overlap=30)):
            if is_noisy_chunk(chunk_text):
                continue
            section_name = detect_section(chunk_text)
            stored_text = build_stored_text(
                title=title,
                category=category,
                section=section_name,
                source=source,
                content=chunk_text,
                url=url,
            )
            all_chunks.append(
                {
                    "id": f"{base_id}_chunk_{index}",
                    "text": stored_text,
                    "metadata": {
                        "title": title,
                        "category": category,
                        "section": section_name,
                        "source": source,
                        "url": url,
                        "chunk_index": index,
                        "disease": disease,
                        "enriched": "false",
                    },
                }
            )

    return all_chunks


def ingest_into_chroma():
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL_NAME
    )
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"[INFO] Old collection '{COLLECTION_NAME}' deleted.")
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
    )

    chunks = read_llm_enriched_documents()
    ingest_mode = "llm_enriched"
    if not chunks:
        ingest_mode = "silver_fallback"
        chunks = read_silver_documents()

    if not chunks:
        print("[WARNING] No chunks found in MinIO.")
        return

    ids = [chunk["id"] for chunk in chunks]
    texts = [chunk["text"] for chunk in chunks]
    metadatas = [chunk["metadata"] for chunk in chunks]
    collection.add(ids=ids, documents=texts, metadatas=metadatas)

    print(f"[DONE] {len(chunks)} chunks inserted into ChromaDB (mode={ingest_mode}).")


if __name__ == "__main__":
    ingest_into_chroma()
