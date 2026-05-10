import logging

from chatbot.llm_generator import (
    MODEL,
    WEB_SEARCH_MODEL,
    detect_question_language,
    generate_answer,
    generate_web_answer,
    get_no_context_message,
)
from chatbot.rag_pipeline import detect_main_topic, extract_subject_tokens, retrieve_local_context
from chatbot.web_search import retrieve_web_context

logger = logging.getLogger(__name__)

FOLLOW_UP_TOKENS = {
    "yes", "yeah", "yep", "sure", "ok", "okay", "please", "share", "guidance",
    "more", "continue", "next", "that", "this", "those", "them", "it", "about",
    "talked", "tell", "advice", "help", "also", "then", "now", "good", "fine",
}

SYMPTOM_MARKERS = {
    "en": {
        "fever", "temperature", "headache", "fatigue", "tired", "tiredness", "cough",
        "sore throat", "dizziness", "dizzy", "nausea", "vomiting", "pain", "chills",
        "weakness", "shortness of breath", "breathing", "vertigo",
    },
    "fr": {
        "fievre", "fièvre", "maux de tete", "mal de tete", "fatigue", "toux",
        "mal a la gorge", "mal à la gorge", "vertige", "vertiges", "nausée",
        "nausées", "douleur", "douleurs", "frissons", "essoufflement", "respirer",
    },
    "es": {
        "fiebre", "dolor de cabeza", "fatiga", "tos", "dolor de garganta", "mareo",
        "mareos", "nausea", "nauseas", "dolor", "escalofrios", "respirar",
    },
}

FIRST_PERSON_MARKERS = {
    "en": {"i", "i'm", "i am", "my", "me", "since", "for 2 days", "for two days"},
    "fr": {"je", "j'ai", "j ai", "mon", "ma", "mes", "depuis", "merci"},
    "es": {"yo", "tengo", "me siento", "mi", "desde", "gracias"},
}


def is_weak_context(context: str) -> bool:
    if not context:
        return True
    return len(context.strip()) < 120


def is_personal_symptom_narrative(question: str) -> bool:
    text = (question or "").strip().lower()
    if len(text) < 80:
        return False
    if detect_main_topic(text):
        return False

    language = detect_question_language(text)
    symptom_markers = SYMPTOM_MARKERS.get(language, SYMPTOM_MARKERS["en"])
    first_person_markers = FIRST_PERSON_MARKERS.get(language, FIRST_PERSON_MARKERS["en"])

    symptom_hits = sum(1 for marker in symptom_markers if marker in text)
    first_person_hits = sum(1 for marker in first_person_markers if marker in text)

    return symptom_hits >= 2 and first_person_hits >= 1


def get_recent_history_text(history: list[dict] | None):
    if not history:
        return []
    return [item for item in history if item.get("role") in {"user", "assistant"} and item.get("content")]


def is_ambiguous_follow_up(question: str, history: list[dict] | None = None) -> bool:
    if not history:
        return False

    q = (question or "").strip().lower()
    subject_tokens = [token for token in extract_subject_tokens(question) if token not in FOLLOW_UP_TOKENS]

    if detect_main_topic(question):
        return False
    if len(subject_tokens) >= 2:
        return False
    if len(q) <= 40:
        return True

    follow_up_phrases = [
        "tell me more",
        "share the guidance",
        "yes sure",
        "what about that",
        "continue",
        "can you expand",
        "more details",
    ]
    return any(phrase in q for phrase in follow_up_phrases)


def get_last_substantive_user_question(question: str, history: list[dict] | None = None) -> str:
    current = (question or "").strip().lower()
    for item in reversed(get_recent_history_text(history)):
        if item.get("role") != "user":
            continue
        content = (item.get("content") or "").strip()
        if not content or content.lower() == current:
            continue
        subject_tokens = [token for token in extract_subject_tokens(content) if token not in FOLLOW_UP_TOKENS]
        if detect_main_topic(content) or len(subject_tokens) >= 1:
            return content
    return ""


def build_effective_question(question: str, history: list[dict] | None = None) -> str:
    if not is_ambiguous_follow_up(question, history):
        return question

    last_question = get_last_substantive_user_question(question, history)
    if not last_question:
        return question

    return f"{last_question}\n\nFollow-up request: {question}"


def merge_sources(main_source: dict, other_sources: list[dict]) -> list[dict]:
    sources = []
    seen = set()
    for source in [main_source, *other_sources]:
        if not source:
            continue
        key = (source.get("title", ""), source.get("url", ""))
        if key in seen:
            continue
        seen.add(key)
        sources.append(source)
    return sources


def sources_to_main_and_others(sources: list[dict]):
    if not sources:
        return {}, []
    return sources[0], sources[1:3]


def ensure_sources(question: str, sources: list[dict]) -> tuple[dict, list[dict]]:
    main_source, other_sources = sources_to_main_and_others(sources)
    if main_source:
        return main_source, other_sources

    web_result = retrieve_web_context(question)
    return web_result.get("main_source", {}), web_result.get("other_sources", [])


def infer_confidence(mode: str, context: str, sources: list[dict], used_openai: bool) -> dict:
    context_length = len((context or "").strip())
    source_count = len(sources)

    if mode == "local_rag" and context_length >= 600:
        return {"level": "high", "label": "High confidence"}
    if mode == "web_search" and used_openai and source_count >= 2:
        return {"level": "high", "label": "High confidence"}
    if mode in {"local_rag", "web_search", "local_rag_fallback"} and context_length >= 200:
        return {"level": "medium", "label": "Medium confidence"}
    return {"level": "low", "label": "Low confidence"}


def build_diagnostics(
    *,
    route: str,
    effective_question: str,
    local_context_length: int,
    web_context_length: int,
    follow_up_detected: bool,
    prioritized_web: bool,
    symptom_narrative: bool,
) -> dict:
    return {
        "route": route,
        "effective_question": effective_question,
        "local_context_length": local_context_length,
        "web_context_length": web_context_length,
        "follow_up_detected": follow_up_detected,
        "prioritized_web": prioritized_web,
        "symptom_narrative": symptom_narrative,
    }


def build_result(
    *,
    question: str,
    mode: str,
    answer: str,
    context: str,
    main_source: dict,
    other_sources: list[dict],
    used_openai: bool,
    diagnostics: dict,
    model_name: str | None = None,
):
    sources = merge_sources(main_source, other_sources)
    confidence = infer_confidence(mode, context, sources, used_openai)
    return {
        "mode": mode,
        "question": question,
        "answer": answer,
        "main_source": main_source,
        "other_sources": other_sources,
        "sources": sources,
        "model": model_name or MODEL,
        "used_openai": used_openai,
        "context_length": len((context or "").strip()),
        "confidence": confidence,
        "diagnostics": diagnostics,
    }


def ask_hybrid_question(
    question: str,
    history: list[dict] | None = None,
    learner_profile: str | None = None,
):
    follow_up_detected = is_ambiguous_follow_up(question, history)
    effective_question = build_effective_question(question, history)
    last_substantive_question = get_last_substantive_user_question(question, history)
    symptom_narrative = is_personal_symptom_narrative(effective_question)
    should_prioritize_web = (
        symptom_narrative
        or (
            follow_up_detected
            and bool(last_substantive_question)
            and not detect_main_topic(last_substantive_question)
        )
    )

    local_context_length = 0
    web_context_length = 0

    if should_prioritize_web:
        web_answer, used_openai, web_sources = generate_web_answer(
            question,
            history=history,
            search_query=effective_question,
            language_hint=detect_question_language(question),
            learner_profile=learner_profile,
        )
        if web_answer:
            main_source, other_sources = ensure_sources(effective_question, web_sources)
            diagnostics = build_diagnostics(
                route="web_priority_follow_up",
                effective_question=effective_question,
                local_context_length=0,
                web_context_length=len(web_answer),
                follow_up_detected=follow_up_detected,
                prioritized_web=True,
                symptom_narrative=symptom_narrative,
            )
            logger.info("Hybrid route=%s mode=web_search question=%r", diagnostics["route"], question)
            return build_result(
                question=question,
                mode="web_search",
                answer=web_answer,
                context=web_answer,
                main_source=main_source,
                other_sources=other_sources,
                used_openai=used_openai,
                diagnostics=diagnostics,
                model_name=WEB_SEARCH_MODEL if used_openai else MODEL,
            )

        web_result = retrieve_web_context(effective_question)
        web_context_length = len((web_result["context"] or "").strip())
        if web_result["context"]:
            answer, used_openai = generate_answer(
                question,
                web_result["context"],
                history=history,
                learner_profile=learner_profile,
            )
            diagnostics = build_diagnostics(
                route="web_priority_follow_up_fallback",
                effective_question=effective_question,
                local_context_length=0,
                web_context_length=web_context_length,
                follow_up_detected=follow_up_detected,
                prioritized_web=True,
                symptom_narrative=symptom_narrative,
            )
            logger.info("Hybrid route=%s mode=web_search question=%r", diagnostics["route"], question)
            return build_result(
                question=question,
                mode="web_search",
                answer=answer,
                context=web_result["context"],
                main_source=web_result["main_source"],
                other_sources=web_result["other_sources"],
                used_openai=used_openai,
                diagnostics=diagnostics,
                model_name=MODEL,
            )

    local_result = retrieve_local_context(effective_question)
    local_context_length = len((local_result["context"] or "").strip())
    if not symptom_narrative and not is_weak_context(local_result["context"]):
        answer, used_openai = generate_answer(
            question,
            local_result["context"],
            history=history,
            learner_profile=learner_profile,
        )
        diagnostics = build_diagnostics(
            route="local_rag",
            effective_question=effective_question,
            local_context_length=local_context_length,
            web_context_length=web_context_length,
            follow_up_detected=follow_up_detected,
            prioritized_web=should_prioritize_web,
            symptom_narrative=symptom_narrative,
        )
        logger.info("Hybrid route=%s mode=local_rag question=%r", diagnostics["route"], question)
        return build_result(
            question=question,
            mode="local_rag",
            answer=answer,
            context=local_result["context"],
            main_source=local_result["main_source"],
            other_sources=local_result["other_sources"],
            used_openai=used_openai,
            diagnostics=diagnostics,
            model_name=MODEL,
        )

    web_answer, used_openai, web_sources = generate_web_answer(
        question,
        history=history,
        search_query=effective_question,
        language_hint=detect_question_language(question),
        learner_profile=learner_profile,
    )
    if web_answer:
        main_source, other_sources = ensure_sources(effective_question, web_sources)
        diagnostics = build_diagnostics(
            route="web_openai",
            effective_question=effective_question,
            local_context_length=local_context_length,
            web_context_length=len(web_answer),
            follow_up_detected=follow_up_detected,
            prioritized_web=should_prioritize_web,
            symptom_narrative=symptom_narrative,
        )
        logger.info("Hybrid route=%s mode=web_search question=%r", diagnostics["route"], question)
        return build_result(
            question=question,
            mode="web_search",
            answer=web_answer,
            context=web_answer,
            main_source=main_source,
            other_sources=other_sources,
            used_openai=used_openai,
            diagnostics=diagnostics,
            model_name=WEB_SEARCH_MODEL if used_openai else MODEL,
        )

    web_result = retrieve_web_context(effective_question)
    web_context_length = len((web_result["context"] or "").strip())
    if web_result["context"]:
        answer, used_openai = generate_answer(
            question,
            web_result["context"],
            history=history,
            learner_profile=learner_profile,
        )
        diagnostics = build_diagnostics(
            route="web_classic_fallback",
            effective_question=effective_question,
            local_context_length=local_context_length,
            web_context_length=web_context_length,
            follow_up_detected=follow_up_detected,
            prioritized_web=should_prioritize_web,
            symptom_narrative=symptom_narrative,
        )
        logger.info("Hybrid route=%s mode=web_search question=%r", diagnostics["route"], question)
        return build_result(
            question=question,
            mode="web_search",
            answer=answer,
            context=web_result["context"],
            main_source=web_result["main_source"],
            other_sources=web_result["other_sources"],
            used_openai=used_openai,
            diagnostics=diagnostics,
            model_name=MODEL,
        )

    if local_result["context"] and not symptom_narrative:
        answer, used_openai = generate_answer(
            question,
            local_result["context"],
            history=history,
            learner_profile=learner_profile,
        )
        diagnostics = build_diagnostics(
            route="local_fallback",
            effective_question=effective_question,
            local_context_length=local_context_length,
            web_context_length=web_context_length,
            follow_up_detected=follow_up_detected,
            prioritized_web=should_prioritize_web,
            symptom_narrative=symptom_narrative,
        )
        logger.info("Hybrid route=%s mode=local_rag_fallback question=%r", diagnostics["route"], question)
        return build_result(
            question=question,
            mode="local_rag_fallback",
            answer=answer,
            context=local_result["context"],
            main_source=local_result["main_source"],
            other_sources=local_result["other_sources"],
            used_openai=used_openai,
            diagnostics=diagnostics,
            model_name=MODEL,
        )

    diagnostics = build_diagnostics(
        route="no_context",
        effective_question=effective_question,
        local_context_length=local_context_length,
        web_context_length=web_context_length,
        follow_up_detected=follow_up_detected,
        prioritized_web=should_prioritize_web,
        symptom_narrative=symptom_narrative,
    )
    logger.warning("Hybrid route=%s mode=no_context question=%r", diagnostics["route"], question)
    return build_result(
        question=question,
        mode="no_context",
        answer=get_no_context_message(question),
        context="",
        main_source={},
        other_sources=[],
        used_openai=False,
        diagnostics=diagnostics,
        model_name=MODEL,
    )


if __name__ == "__main__":
    print(ask_hybrid_question("What causes COVID-19?"))
