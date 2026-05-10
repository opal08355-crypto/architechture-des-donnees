import logging
import os
import time
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from chatbot.dashboard_data import fetch_dashboard_data
from chatbot.hybrid_pipeline import ask_hybrid_question
from chatbot.llm_generator import MODEL, USE_AZURE_OPENAI
from chatbot.learning_store import (
    export_finetune_jsonl,
    generate_turn_id,
    learning_summary,
    record_feedback,
    record_interaction,
)
from chatbot.metrics_store import read_chatbot_metrics, record_chat_interaction

logging.basicConfig(
    level=os.getenv("CHATBOT_LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Medical Assistance Chatbot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"] = Field(..., description="Message role")
    content: str = Field(..., min_length=1, description="Message content")


class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=1)
    history: list[ChatMessage] = Field(default_factory=list)
    learner_profile: str = Field(default_factory=lambda: os.getenv("CHATBOT_LEARNER_PROFILE", "Engineering Student"))


class FeedbackRequest(BaseModel):
    turn_id: str = Field(..., min_length=4)
    rating: int = Field(..., ge=1, le=5)
    note: str = Field(default="", max_length=2500)
    preferred_answer: str = Field(default="", max_length=10000)


class ExportDatasetRequest(BaseModel):
    output_path: str = Field(default="chatbot/learning_data/finetune_dataset.jsonl", min_length=3)
    min_rating: int = Field(default=4, ge=1, le=5)


@app.get("/")
def home():
    return FileResponse("chatbot/index.html")


@app.get("/dashboard")
def dashboard_page():
    return FileResponse("dashboard/index.html")


@app.get("/health")
def health():
    if USE_AZURE_OPENAI:
        api_key = (os.getenv("AZURE_OPENAI_API_KEY") or "").strip()
        provider = "azure_openai"
    else:
        api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
        provider = "openai"
    return {
        "status": "ok",
        "app": "medical-assistance-chatbot",
        "openai_configured": bool(api_key),
        "provider": provider,
        "model": MODEL,
        "learner_profile": os.getenv("CHATBOT_LEARNER_PROFILE", "Engineering Student"),
        "ui_language": "fr",
        "logging_level": os.getenv("CHATBOT_LOG_LEVEL", "INFO"),
    }


@app.get("/api/dashboard")
def dashboard_data():
    payload = fetch_dashboard_data()
    logger.info(
        "Dashboard payload source_kind=%s total_articles=%s warnings=%d",
        payload.get("source_kind"),
        payload.get("kpis", {}).get("total_articles"),
        len(payload.get("warnings", [])),
    )
    return payload


@app.get("/api/chatbot-metrics")
def chatbot_metrics():
    payload = read_chatbot_metrics()
    logger.info(
        "Chatbot metrics total_questions=%s avg_latency_ms=%s",
        payload.get("total_questions"),
        payload.get("avg_latency_ms"),
    )
    return payload


@app.get("/api/learning/summary")
def get_learning_summary():
    payload = learning_summary()
    logger.info(
        "Learning summary interactions=%d feedback=%d ready=%d",
        payload.get("interactions", 0),
        payload.get("feedback_items", 0),
        payload.get("finetune_ready_examples", 0),
    )
    return payload


@app.post("/feedback")
def save_feedback(request: FeedbackRequest):
    record_feedback(
        turn_id=request.turn_id.strip(),
        rating=request.rating,
        note=request.note.strip(),
        preferred_answer=request.preferred_answer.strip(),
    )
    logger.info("Feedback saved turn_id=%s rating=%d", request.turn_id, request.rating)
    return {"status": "ok", "message": "feedback_saved"}


@app.post("/api/learning/export")
def export_learning_dataset(request: ExportDatasetRequest):
    result = export_finetune_jsonl(
        output_path=request.output_path.strip(),
        min_rating=request.min_rating,
    )
    logger.info(
        "Learning dataset exported output=%s examples=%d min_rating=%d",
        result["output_path"],
        result["examples"],
        result["min_rating"],
    )
    return {"status": "ok", **result}


@app.post("/ask")
def ask_question(request: QuestionRequest):
    clean_question = request.question.strip()
    learner_profile = request.learner_profile.strip() or os.getenv("CHATBOT_LEARNER_PROFILE", "Engineering Student")
    history = [message.model_dump() for message in request.history]
    logger.info(
        "Incoming question=%r history_items=%d learner_profile=%r",
        clean_question,
        len(history),
        learner_profile,
    )
    started_at = time.perf_counter()
    turn_id = generate_turn_id()

    result = ask_hybrid_question(
        question=clean_question,
        history=history,
        learner_profile=learner_profile,
    )
    latency_ms = int((time.perf_counter() - started_at) * 1000)

    record_chat_interaction(
        question=clean_question,
        mode=result["mode"],
        confidence_level=result["confidence"]["level"],
        used_openai=result["used_openai"],
        latency_ms=latency_ms,
        sources=result["sources"],
    )
    record_interaction(
        turn_id=turn_id,
        question=clean_question,
        answer=result["answer"],
        mode=result["mode"],
        confidence_level=result["confidence"]["level"],
        learner_profile=learner_profile,
        sources=result["sources"],
    )

    logger.info(
        "Answered question=%r mode=%s confidence=%s sources=%d latency_ms=%d route=%s",
        clean_question,
        result["mode"],
        result["confidence"]["level"],
        len(result["sources"]),
        latency_ms,
        result["diagnostics"].get("route"),
    )

    return {
        "question": result["question"],
        "mode": result["mode"],
        "answer": result["answer"],
        "main_source": result["main_source"],
        "other_sources": result["other_sources"],
        "sources": result["sources"],
        "model": result["model"],
        "turn_id": turn_id,
        "learner_profile": learner_profile,
        "used_openai": result["used_openai"],
        "context_length": result["context_length"],
        "confidence": result["confidence"],
        "latency_ms": latency_ms,
        "diagnostics": result["diagnostics"],
        "disclaimer": "Ce chatbot fournit des informations generales et ne remplace pas un avis medical professionnel.",
    }
