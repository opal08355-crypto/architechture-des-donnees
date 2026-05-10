import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from chatbot.llm_generator import detect_question_language
from chatbot.rag_pipeline import detect_main_topic, extract_subject_tokens


METRICS_PATH = Path("chatbot/runtime_metrics.json")
_METRICS_LOCK = Lock()


def utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_metrics() -> dict:
    return {
        "generated_at": utc_iso_now(),
        "total_questions": 0,
        "latency_total_ms": 0,
        "avg_latency_ms": 0.0,
        "openai_calls": 0,
        "mode_counts": {},
        "confidence_counts": {},
        "language_counts": {},
        "topic_counts": {},
        "source_counts": {},
        "last_question": "",
    }


def normalize_counter(mapping: dict | None) -> dict:
    normalized = {}
    for key, value in (mapping or {}).items():
        if key is None:
            continue
        label = str(key).strip()
        if not label:
            continue
        normalized[label] = int(value or 0)
    return normalized


def load_metrics() -> dict:
    if not METRICS_PATH.exists():
        return default_metrics()

    try:
        payload = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return default_metrics()

    metrics = default_metrics()
    metrics.update(payload if isinstance(payload, dict) else {})
    metrics["mode_counts"] = normalize_counter(metrics.get("mode_counts"))
    metrics["confidence_counts"] = normalize_counter(metrics.get("confidence_counts"))
    metrics["language_counts"] = normalize_counter(metrics.get("language_counts"))
    metrics["topic_counts"] = normalize_counter(metrics.get("topic_counts"))
    metrics["source_counts"] = normalize_counter(metrics.get("source_counts"))
    metrics["total_questions"] = int(metrics.get("total_questions", 0) or 0)
    metrics["latency_total_ms"] = int(metrics.get("latency_total_ms", 0) or 0)
    metrics["openai_calls"] = int(metrics.get("openai_calls", 0) or 0)
    metrics["avg_latency_ms"] = float(metrics.get("avg_latency_ms", 0) or 0)
    metrics["last_question"] = str(metrics.get("last_question", "") or "")
    return metrics


def save_metrics(metrics: dict) -> None:
    metrics = dict(metrics or {})
    metrics["generated_at"] = utc_iso_now()
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = METRICS_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(metrics, ensure_ascii=True, indent=2), encoding="utf-8")
    tmp_path.replace(METRICS_PATH)


def increment_counter(mapping: dict, key: str) -> None:
    if not key:
        return
    mapping[key] = int(mapping.get(key, 0) or 0) + 1


def detect_topic_label(question: str) -> str:
    topic = detect_main_topic(question)
    if topic:
        return topic

    subject_tokens = extract_subject_tokens(question)
    if subject_tokens:
        return " ".join(subject_tokens[:2])
    return "general"


def record_chat_interaction(
    *,
    question: str,
    mode: str,
    confidence_level: str,
    used_openai: bool,
    latency_ms: int,
    sources: list[dict] | None = None,
) -> None:
    with _METRICS_LOCK:
        metrics = load_metrics()
        metrics["total_questions"] += 1
        metrics["latency_total_ms"] += max(int(latency_ms or 0), 0)
        if metrics["total_questions"] > 0:
            metrics["avg_latency_ms"] = round(
                metrics["latency_total_ms"] / metrics["total_questions"],
                1,
            )

        if used_openai:
            metrics["openai_calls"] += 1

        increment_counter(metrics["mode_counts"], mode or "unknown")
        increment_counter(metrics["confidence_counts"], confidence_level or "unknown")
        increment_counter(metrics["language_counts"], detect_question_language(question))
        increment_counter(metrics["topic_counts"], detect_topic_label(question))

        source_counter = Counter()
        for source in sources or []:
            label = (source or {}).get("source", "")
            if label:
                source_counter[label] += 1
        for label, count in source_counter.items():
            metrics["source_counts"][label] = int(metrics["source_counts"].get(label, 0) or 0) + int(count)

        metrics["last_question"] = (question or "").strip()[:180]
        save_metrics(metrics)


def rows_from_counter(mapping: dict, limit: int = 8) -> list[dict]:
    rows = [{"label": key, "value": int(value)} for key, value in normalize_counter(mapping).items()]
    rows.sort(key=lambda item: item["value"], reverse=True)
    return rows[:limit]


def read_chatbot_metrics() -> dict:
    with _METRICS_LOCK:
        metrics = load_metrics()

    total_questions = metrics["total_questions"]
    openai_usage_rate = round((metrics["openai_calls"] / total_questions) * 100, 1) if total_questions else 0.0

    return {
        "generated_at": metrics.get("generated_at", utc_iso_now()),
        "total_questions": total_questions,
        "avg_latency_ms": float(metrics.get("avg_latency_ms", 0) or 0),
        "openai_usage_rate": openai_usage_rate,
        "last_question": metrics.get("last_question", ""),
        "modes": rows_from_counter(metrics.get("mode_counts"), limit=8),
        "confidence": rows_from_counter(metrics.get("confidence_counts"), limit=6),
        "languages": rows_from_counter(metrics.get("language_counts"), limit=6),
        "topics": rows_from_counter(metrics.get("topic_counts"), limit=8),
        "sources": rows_from_counter(metrics.get("source_counts"), limit=6),
    }
