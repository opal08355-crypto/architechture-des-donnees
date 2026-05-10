import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4


LEARNING_DIR = Path("chatbot/learning_data")
INTERACTIONS_PATH = LEARNING_DIR / "interactions.jsonl"
FEEDBACK_PATH = LEARNING_DIR / "feedback.jsonl"
_STORE_LOCK = Lock()


def utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_store_dir() -> None:
    LEARNING_DIR.mkdir(parents=True, exist_ok=True)


def generate_turn_id() -> str:
    return f"turn-{uuid4().hex[:16]}"


def append_jsonl(path: Path, payload: dict) -> None:
    ensure_store_dir()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except Exception:
                continue
            if isinstance(data, dict):
                yield data


def record_interaction(
    *,
    turn_id: str,
    question: str,
    answer: str,
    mode: str,
    confidence_level: str,
    learner_profile: str,
    sources: list[dict] | None = None,
) -> None:
    payload = {
        "timestamp": utc_iso_now(),
        "turn_id": turn_id,
        "question": (question or "").strip(),
        "answer": (answer or "").strip(),
        "mode": mode or "unknown",
        "confidence_level": confidence_level or "unknown",
        "learner_profile": (learner_profile or "").strip(),
        "sources": sources or [],
    }
    with _STORE_LOCK:
        append_jsonl(INTERACTIONS_PATH, payload)


def record_feedback(
    *,
    turn_id: str,
    rating: int,
    note: str = "",
    preferred_answer: str = "",
) -> None:
    payload = {
        "timestamp": utc_iso_now(),
        "turn_id": (turn_id or "").strip(),
        "rating": int(rating),
        "note": (note or "").strip(),
        "preferred_answer": (preferred_answer or "").strip(),
    }
    with _STORE_LOCK:
        append_jsonl(FEEDBACK_PATH, payload)


def _feedback_index() -> dict:
    index = {}
    for item in iter_jsonl(FEEDBACK_PATH) or []:
        turn_id = str(item.get("turn_id", "")).strip()
        if not turn_id:
            continue
        index[turn_id] = item
    return index


def build_finetune_examples(min_rating: int = 4) -> list[dict]:
    feedback_by_turn = _feedback_index()
    examples = []

    for item in iter_jsonl(INTERACTIONS_PATH) or []:
        turn_id = str(item.get("turn_id", "")).strip()
        if not turn_id:
            continue
        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        profile = str(item.get("learner_profile", "")).strip()
        if not question or not answer:
            continue

        feedback = feedback_by_turn.get(turn_id)
        if feedback:
            rating = int(feedback.get("rating", 0) or 0)
            if rating < min_rating:
                continue
            preferred_answer = str(feedback.get("preferred_answer", "")).strip()
            if preferred_answer:
                answer = preferred_answer

        system_text = (
            "You are a careful medical assistant. "
            "Answer in the same language as the user and keep explanations structured. "
            f"Adapt depth to learner profile: {profile or 'general learner'}."
        )
        examples.append(
            {
                "messages": [
                    {"role": "system", "content": system_text},
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": answer},
                ]
            }
        )
    return examples


def export_finetune_jsonl(output_path: str, min_rating: int = 4) -> dict:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    examples = build_finetune_examples(min_rating=min_rating)
    with path.open("w", encoding="utf-8") as handle:
        for item in examples:
            handle.write(json.dumps(item, ensure_ascii=True) + "\n")
    return {
        "output_path": str(path),
        "examples": len(examples),
        "min_rating": int(min_rating),
    }


def learning_summary() -> dict:
    interactions = list(iter_jsonl(INTERACTIONS_PATH) or [])
    feedbacks = list(iter_jsonl(FEEDBACK_PATH) or [])
    feedback_by_turn = _feedback_index()

    positive_feedback = sum(1 for item in feedbacks if int(item.get("rating", 0) or 0) >= 4)
    summary = {
        "interactions": len(interactions),
        "feedback_items": len(feedbacks),
        "positive_feedback": positive_feedback,
        "finetune_ready_examples": len(build_finetune_examples(min_rating=4)),
    }

    if feedback_by_turn:
        scores = [int(item.get("rating", 0) or 0) for item in feedback_by_turn.values()]
        summary["average_rating"] = round(sum(scores) / len(scores), 2)
    else:
        summary["average_rating"] = 0.0
    return summary
