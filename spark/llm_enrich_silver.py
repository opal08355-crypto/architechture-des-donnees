import json
import os
import re
from io import BytesIO

import httpx
from minio import Minio
from openai import OpenAI


MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "admin12345")
SILVER_BUCKET = os.getenv("MINIO_SILVER_BUCKET", "silver")
GOLD_BUCKET = os.getenv("MINIO_GOLD_BUCKET", "gold")
SILVER_PREFIX = os.getenv("SILVER_PREFIX", "medical_articles_clean/")
LLM_GOLD_PREFIX = os.getenv("LLM_GOLD_PREFIX", "llm_enriched/")
LLM_MAX_RECORDS = int(os.getenv("LLM_ENRICH_MAX_RECORDS", "0") or "0")
LLM_SKIP_EXISTING = os.getenv("LLM_ENRICH_SKIP_EXISTING", "true").lower() == "true"
LLM_INPUT_CHAR_LIMIT = int(os.getenv("LLM_ENRICH_INPUT_CHAR_LIMIT", "4500") or "4500")
LLM_USE_WEB_CONTEXT = os.getenv("LLM_ENRICH_USE_WEB_CONTEXT", "true").lower() == "true"
LLM_WEB_CONTEXT_CHAR_LIMIT = int(os.getenv("LLM_ENRICH_WEB_CHAR_LIMIT", "2500") or "2500")
LLM_MODEL = os.getenv("LLM_ENRICH_MODEL", "") or os.getenv("OPENAI_MODEL", "gpt-4o")
USE_AZURE_OPENAI = os.getenv("USE_AZURE_OPENAI", "false").lower() == "true"


def get_minio_client():
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )


def ensure_bucket_exists(client: Minio, bucket_name: str):
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)
        print(f"[INFO] Bucket created: {bucket_name}")


def list_objects(client: Minio, bucket_name: str, prefix: str):
    return client.list_objects(bucket_name, prefix=prefix, recursive=True)


def read_json(client: Minio, bucket_name: str, object_name: str) -> dict:
    response = client.get_object(bucket_name, object_name)
    try:
        return json.loads(response.read().decode("utf-8"))
    finally:
        response.close()
        response.release_conn()


def upload_json(client: Minio, bucket_name: str, object_name: str, payload: dict):
    raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    stream = BytesIO(raw)
    client.put_object(
        bucket_name,
        object_name,
        stream,
        length=len(raw),
        content_type="application/json",
    )
    print(f"[OK] Uploaded: {bucket_name}/{object_name}")


def build_azure_base_url(endpoint: str) -> str:
    raw_endpoint = (endpoint or "").strip().rstrip("/")
    if not raw_endpoint:
        return ""
    if "/openai/v1/" in raw_endpoint:
        raw_endpoint = raw_endpoint.split("/openai/v1/", 1)[0]
    elif raw_endpoint.endswith("/openai/v1"):
        raw_endpoint = raw_endpoint[: -len("/openai/v1")]
    if raw_endpoint.endswith("/responses"):
        raw_endpoint = raw_endpoint[: -len("/responses")]
    return f"{raw_endpoint}/openai/v1/"


def get_openai_client():
    http_client = httpx.Client(
        timeout=httpx.Timeout(60.0, connect=20.0),
        trust_env=False,
    )
    if USE_AZURE_OPENAI:
        api_key = (os.getenv("AZURE_OPENAI_API_KEY") or "").strip()
        endpoint = build_azure_base_url((os.getenv("AZURE_OPENAI_ENDPOINT") or "").strip())
        if not api_key or not endpoint:
            return None
        return OpenAI(api_key=api_key, base_url=endpoint, http_client=http_client)
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None
    return OpenAI(api_key=api_key, http_client=http_client)


def strip_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def trim_for_prompt(text: str, max_chars: int) -> str:
    cleaned = strip_text(text)
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars].rsplit(" ", 1)[0].strip()


def empty_enrichment() -> dict:
    return {
        "disease": "",
        "summary": "",
        "key_symptoms": [],
        "causes": [],
        "treatments": [],
        "medications": [],
        "red_flags": [],
        "contraindications": [],
        "preventive_tips": [],
        "confidence": "low",
        "language": "",
    }


def heuristic_enrichment(record: dict) -> dict:
    content = strip_text(record.get("content", ""))
    title = strip_text(record.get("title", ""))
    language = strip_text(record.get("language", "unknown"))
    summary = content[:360].rsplit(" ", 1)[0].strip() if content else ""

    result = empty_enrichment()
    result["disease"] = title
    result["summary"] = summary
    result["language"] = language
    result["confidence"] = "low"

    content_l = content.lower()
    if "symptom" in content_l or "sympt" in content_l:
        result["key_symptoms"] = [summary] if summary else []
    if "treat" in content_l or "therapy" in content_l or "medic" in content_l:
        result["treatments"] = [summary] if summary else []
    return result


def parse_json_object(text: str) -> dict | None:
    candidate = (text or "").strip()
    if not candidate:
        return None
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(candidate[start : end + 1])
    except Exception:
        return None


def normalize_enrichment(payload: dict, fallback_language: str) -> dict:
    normalized = empty_enrichment()
    for key in normalized:
        value = payload.get(key)
        if isinstance(normalized[key], list):
            if isinstance(value, list):
                normalized[key] = [strip_text(str(item)) for item in value if strip_text(str(item))]
            elif isinstance(value, str) and strip_text(value):
                normalized[key] = [strip_text(value)]
        else:
            normalized[key] = strip_text(str(value)) if value is not None else ""

    if normalized["confidence"] not in {"low", "medium", "high"}:
        normalized["confidence"] = "medium" if normalized["summary"] else "low"
    if not normalized["language"]:
        normalized["language"] = fallback_language or "unknown"
    return normalized


def build_web_query(record: dict) -> str:
    title = strip_text(record.get("title", ""))
    category = strip_text(record.get("category", ""))
    query_parts = [title]
    if category and category != "medical_info":
        query_parts.append(category)
    query = " ".join(part for part in query_parts if part)
    return strip_text(query) or "medical condition overview"


def collect_web_sources(result: dict) -> list[dict]:
    sources = []
    for item in [result.get("main_source", {}), *(result.get("other_sources", []) or [])]:
        url = strip_text((item or {}).get("url", ""))
        if not url:
            continue
        sources.append(
            {
                "title": strip_text((item or {}).get("title", "")) or "Web source",
                "source": strip_text((item or {}).get("source", "")) or "Web Search",
                "url": url,
            }
        )
    return sources[:3]


def fetch_web_context(record: dict) -> dict:
    query = build_web_query(record)
    empty_result = {
        "enabled": LLM_USE_WEB_CONTEXT,
        "query": query,
        "used": False,
        "method": "disabled",
        "context": "",
        "sources": [],
    }
    if not LLM_USE_WEB_CONTEXT:
        return empty_result

    try:
        from chatbot.web_search import retrieve_web_context
    except Exception as exc:
        print(f"[WARN] Web context import failed for enrichment: {exc}")
        empty_result["method"] = "import_failed"
        return empty_result

    try:
        web_result = retrieve_web_context(query)
        context = trim_for_prompt(web_result.get("context", ""), LLM_WEB_CONTEXT_CHAR_LIMIT)
        sources = collect_web_sources(web_result)
        return {
            "enabled": True,
            "query": query,
            "used": bool(context),
            "method": "trusted_web_search" if context else "trusted_web_search_empty",
            "context": context,
            "sources": sources,
        }
    except Exception as exc:
        print(f"[WARN] Web context lookup failed for query={query!r} error={exc}")
        empty_result["method"] = "lookup_failed"
        return empty_result


def format_web_context_for_prompt(web_payload: dict) -> str:
    context = strip_text(web_payload.get("context", ""))
    if not context:
        return ""

    sections = [f"Supplementary trusted medical web context:\n{context}"]
    sources = web_payload.get("sources", [])
    if sources:
        source_lines = []
        for source in sources:
            title = strip_text(source.get("title", "")) or "Web source"
            url = strip_text(source.get("url", ""))
            source_lines.append(f"- {title} | {url}")
        sections.append("Supplementary web sources:\n" + "\n".join(source_lines))
    return "\n\n".join(sections)


def build_messages(record: dict, text_for_prompt: str, web_payload: dict | None = None) -> list[dict]:
    language = strip_text(record.get("language", "unknown"))
    web_context_block = format_web_context_for_prompt(web_payload or {})
    return [
        {
            "role": "system",
            "content": (
                "You are a medical data enrichment engine. Return valid JSON only. "
                "Do not add markdown, code fences, or explanations."
            ),
        },
        {
            "role": "user",
            "content": (
                "Extract structured medical fields from this article.\n"
                "Return JSON with exactly these keys:\n"
                "disease, summary, key_symptoms, causes, treatments, medications, "
                "red_flags, contraindications, preventive_tips, confidence, language.\n"
                "Rules:\n"
                "- confidence must be one of: low, medium, high\n"
                "- Arrays must contain short strings\n"
                "- Keep language equal to article language\n"
                "- Use the article as the primary source\n"
                "- Use supplementary web context only to complete missing fields or clarify the article\n"
                "- If article and web context disagree, stay cautious and lower confidence\n"
                f"- article_language: {language}\n"
                f"- title: {strip_text(record.get('title', ''))}\n"
                f"- source: {strip_text(record.get('source', ''))}\n"
                f"- url: {strip_text(record.get('url', ''))}\n"
                f"- content: {text_for_prompt}"
                + (f"\n\n{web_context_block}" if web_context_block else "")
            ),
        },
    ]


def enrich_with_llm(client: OpenAI | None, record: dict, web_payload: dict | None = None) -> tuple[dict, str]:
    if client is None:
        return heuristic_enrichment(record), "heuristic_no_client"

    text_for_prompt = trim_for_prompt(record.get("content", ""), LLM_INPUT_CHAR_LIMIT)
    if not text_for_prompt:
        return heuristic_enrichment(record), "heuristic_empty_content"

    web_payload = web_payload or {}

    try:
        completion = client.chat.completions.create(
            model=LLM_MODEL,
            messages=build_messages(record, text_for_prompt, web_payload=web_payload),
            temperature=0.1,
        )
        content = completion.choices[0].message.content or ""
        parsed = parse_json_object(content)
        if parsed:
            method = "llm_chat_completions_web_context" if web_payload.get("used") else "llm_chat_completions"
            return normalize_enrichment(parsed, record.get("language", "unknown")), method
    except Exception as exc:
        print(f"[WARN] LLM enrichment failed for url={record.get('url','')} error={exc}")

    return heuristic_enrichment(record), "heuristic_fallback"


def build_output_path(source_object_name: str) -> str:
    filename = source_object_name.split("/")[-1]
    return f"{LLM_GOLD_PREFIX}{filename}"


def object_exists(client: Minio, bucket_name: str, object_name: str) -> bool:
    try:
        client.stat_object(bucket_name, object_name)
        return True
    except Exception:
        return False


def enrich_silver_to_llm_gold():
    client = get_minio_client()
    ensure_bucket_exists(client, GOLD_BUCKET)
    llm_client = get_openai_client()

    processed = 0
    skipped = 0
    failed = 0

    for obj in list_objects(client, SILVER_BUCKET, SILVER_PREFIX):
        source_name = obj.object_name
        target_name = build_output_path(source_name)

        if LLM_SKIP_EXISTING and object_exists(client, GOLD_BUCKET, target_name):
            skipped += 1
            print(f"[SKIP] Already exists: {target_name}")
            continue

        try:
            record = read_json(client, SILVER_BUCKET, source_name)
            web_payload = fetch_web_context(record)
            enrichment, method = enrich_with_llm(llm_client, record, web_payload=web_payload)
            output = {
                "title": strip_text(record.get("title", "")),
                "content": strip_text(record.get("content", "")),
                "source": strip_text(record.get("source", "")),
                "url": strip_text(record.get("url", "")),
                "scraped_at": strip_text(record.get("scraped_at", "")),
                "language": strip_text(record.get("language", "")),
                "category": strip_text(record.get("category", "")),
                "content_length": int(record.get("content_length", 0) or 0),
                "llm_enrichment": enrichment,
                "llm_method": method,
                "llm_model": LLM_MODEL,
                "web_context_query": web_payload.get("query", ""),
                "web_context_used": bool(web_payload.get("used")),
                "web_context_method": web_payload.get("method", ""),
                "web_sources": web_payload.get("sources", []),
            }
            upload_json(client, GOLD_BUCKET, target_name, output)
            processed += 1
        except Exception as exc:
            failed += 1
            print(f"[ERROR] Failed to enrich {source_name}: {exc}")

        if LLM_MAX_RECORDS > 0 and processed >= LLM_MAX_RECORDS:
            break

    print(
        f"[DONE] LLM enrichment completed | processed={processed} skipped={skipped} failed={failed} "
        f"bucket={GOLD_BUCKET} prefix={LLM_GOLD_PREFIX}"
    )


if __name__ == "__main__":
    enrich_silver_to_llm_gold()
