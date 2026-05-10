import os
import re
import logging
import unicodedata

import httpx
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger(__name__)

USE_AZURE_OPENAI = (os.getenv("USE_AZURE_OPENAI", "false").lower() == "true")
MODEL = (
    os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
    or os.getenv("OPENAI_MODEL")
    or "gpt-4o"
) if USE_AZURE_OPENAI else (os.getenv("OPENAI_MODEL", "gpt-4o"))
WEB_SEARCH_MODEL = (
    os.getenv("AZURE_OPENAI_WEB_DEPLOYMENT")
    or os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
    or os.getenv("OPENAI_WEB_MODEL")
    or MODEL
) if USE_AZURE_OPENAI else (os.getenv("OPENAI_WEB_MODEL", "gpt-4o-search-preview"))
MAX_HISTORY_MESSAGES = 6
WEB_ALLOWED_DOMAINS = [
    "medlineplus.gov",
    "nhs.uk",
    "who.int",
    "cdc.gov",
]
DEFAULT_LEARNER_PROFILE = os.getenv("CHATBOT_LEARNER_PROFILE", "Engineering Student")

SYMPTOM_FALLBACK_MESSAGES = {
    "fr": """Reponse rapide:
- Je ne peux pas relier ces symptomes de facon fiable a une cause precise avec le contexte disponible.
- Cela peut parfois correspondre a une infection virale ou a un autre probleme general, mais je ne peux pas le confirmer ici.

Ce que vous pouvez faire maintenant:
- Reposez-vous et hydratez-vous correctement.
- Surveillez l'evolution de la fievre, des vertiges, de la toux et de l'etat general.
- Si vous prenez deja un medicament courant pour la fievre, respectez uniquement la notice ou l'avis de votre professionnel de sante.

Quand consulter rapidement:
- si la fievre dure, s'aggrave, ou si vous vous sentez de plus en plus faible
- si les vertiges deviennent importants, si vous avez du mal a respirer, une douleur thoracique, une confusion, ou des signes de deshydratation
- si vous avez un doute important ou si l'evolution vous inquiete

Conseil prudent:
- Comme vous decrivez plusieurs symptomes personnels, demander un avis medical reste l'option la plus sure.""",
    "en": """Quick answer:
- I cannot reliably link those symptoms to one specific cause from the available context.
- This can sometimes happen with a viral infection or another general condition, but I cannot confirm that here.

What you can do now:
- Rest and stay well hydrated.
- Monitor how the fever, dizziness, cough, and overall fatigue evolve.
- If you are already using a common fever medicine, follow only the label directions or your clinician's advice.

When to seek care promptly:
- if the fever lasts, gets worse, or you feel progressively weaker
- if the dizziness becomes significant, or if you develop breathing trouble, chest pain, confusion, or signs of dehydration
- if you are worried or feel the situation is not improving

Cautious guidance:
- Because you describe several personal symptoms, getting medical advice is still the safest next step.""",
    "es": """Respuesta rapida:
- No puedo relacionar esos sintomas con una causa especifica de forma fiable con el contexto disponible.
- A veces esto puede ocurrir con una infeccion viral u otro problema general, pero no puedo confirmarlo aqui.

Que puede hacer ahora:
- Descanse y mantengase bien hidratado.
- Vigile como evolucionan la fiebre, los mareos, la tos y el estado general.
- Si ya esta usando un medicamento comun para la fiebre, siga solo las indicaciones del envase o de su profesional de salud.

Cuando consultar pronto:
- si la fiebre dura, empeora, o se siente cada vez mas debil
- si los mareos se vuelven importantes, o si presenta dificultad para respirar, dolor en el pecho, confusion o signos de deshidratacion
- si tiene una preocupacion importante o nota que no mejora

Orientacion prudente:
- Como describe varios sintomas personales, buscar atencion medica sigue siendo la opcion mas segura.""",
}

LANGUAGE_INSTRUCTIONS = {
    "fr": "Answer only in French.",
    "en": "Answer only in English.",
    "es": "Answer only in Spanish.",
    "ar": "Answer only in Arabic.",
}

FALLBACK_MESSAGES = {
    "fr": "Je n'ai pas trouve assez d'informations fiables pour repondre clairement.",
    "en": "I could not find enough reliable information to answer that clearly.",
    "es": "No encontre suficiente informacion fiable para responder con claridad.",
    "ar": "لم أجد معلومات موثوقة كافية للإجابة بوضوح.",
}

SYSTEM_PROMPT = """You are a careful medical information assistant.
Use only the provided context.
Answer in the same language as the user's latest question.
Write naturally, clearly, and in a warm conversational style.
Use a structured format with short section titles and compact bullet points when useful.
Do not use markdown links, raw URLs, or inline source citations in the answer body.
The UI will show the sources separately.
When appropriate, follow this structure:
Quick answer:
- ...

Key points:
- ...

What to do next:
- ...

When to seek care:
- ...

Do not copy noisy website text.
Do not invent facts.
Do not provide diagnosis, emergency triage, or personal treatment plans.
If the user describes personal symptoms, stay cautious, avoid guessing a disease, and give only general guidance plus when to seek care.
If the context is weak or incomplete, say so clearly and keep the answer cautious."""

WEB_SYSTEM_PROMPT = """You are a careful medical information assistant with web access.
Search only for high-quality medical sources and answer in the same language as the user's latest question.
Prefer reliable public-health or medical-reference websites.
Keep the answer concise, factual, easy to read, and clearly structured with short section titles and bullets.
Do not use markdown links, raw URLs, or inline source citations in the answer body.
The interface will show the sources separately.
Do not provide diagnosis or personal treatment plans.
If the user describes personal symptoms, avoid guessing a specific disease and keep the answer focused on general guidance and warning signs.
If good sources are not found, say so clearly."""


def get_client():
    http_client = httpx.Client(
        timeout=httpx.Timeout(45.0, connect=15.0),
        trust_env=False,
    )

    if USE_AZURE_OPENAI:
        api_key = (os.getenv("AZURE_OPENAI_API_KEY") or "").strip()
        endpoint = build_azure_base_url((os.getenv("AZURE_OPENAI_ENDPOINT") or "").strip())
        if not api_key or not endpoint:
            return None
        return OpenAI(
            api_key=api_key,
            base_url=endpoint,
            http_client=http_client,
        )

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None
    return OpenAI(api_key=api_key, http_client=http_client)


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


def detect_question_language(question: str) -> str:
    raw_text = (question or "").strip()
    if not raw_text:
        return "en"

    if re.search(r"[\u0600-\u06FF]", raw_text):
        return "ar"

    normalized = unicodedata.normalize("NFKD", raw_text)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char)).lower()
    padded_text = f" {ascii_text} "
    tokens = set(re.findall(r"[a-z']+", ascii_text))

    french_markers = {
        "bonjour", "pourquoi", "comment", "quels", "quelles", "quelle", "peux",
        "pouvez", "avec", "sans", "dans", "reponse", "symptomes", "traitement",
        "maladie", "pression", "hypertension", "mon", "ma", "mes", "dos", "fait",
        "beaucoup", "mal", "j ai", "je", "douleur", "douleurs", "tete", "gorge",
        "fievre", "depuis", "corps", "peut", "dois", "consulter", "medecin",
        "oui", "non", "merci", "explique", "simplement", "asthme", "moi",
        "pour", "avec", "sans", "chez", "quel", "quelle", "quand",
    }
    spanish_markers = {
        "hola", "como", "porque", "cuales", "puedes", "usted", "sintomas",
        "tratamiento", "enfermedad", "presion", "salud", "dolor", "espalda",
        "mucho", "tengo", "desde", "medico", "gracias",
    }
    english_markers = {
        "what", "how", "why", "can", "could", "should", "symptoms", "treatment",
        "disease", "blood", "pressure", "management", "causes", "back", "pain",
        "my", "does", "help", "doctor", "thanks",
    }

    def score(markers: set[str]) -> int:
        return sum(1 for marker in markers if marker in tokens or f" {marker} " in padded_text)

    french_score = score(french_markers)
    spanish_score = score(spanish_markers)
    english_score = score(english_markers)

    if any(
        char in raw_text
        for char in "\u00e0\u00e2\u00e7\u00e9\u00e8\u00ea\u00eb\u00ee\u00ef\u00f4\u00fb\u00f9\u00fc\u00ff\u0153"
                    "\u00c0\u00c2\u00c7\u00c9\u00c8\u00ca\u00cb\u00ce\u00cf\u00d4\u00db\u00d9\u00dc\u0178\u0152"
    ):
        french_score += 2
    if any(
        char in raw_text
        for char in "\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1\u00bf\u00a1\u00c1\u00c9\u00cd\u00d3\u00da\u00d1"
    ):
        spanish_score += 2

    if french_score > max(spanish_score, english_score):
        return "fr"
    if spanish_score > max(french_score, english_score):
        return "es"
    if english_score > 0:
        return "en"
    return "en"


def is_personal_symptom_question(question: str) -> bool:
    text = (question or "").strip().lower()
    if len(text) < 80:
        return False

    symptom_patterns = [
        "fever", "headache", "fatigue", "cough", "sore throat", "dizziness",
        "fievre", "fièvre", "maux de tete", "mal de tete", "fatigue", "toux",
        "mal a la gorge", "mal à la gorge", "vertige", "vertiges",
        "fiebre", "dolor de cabeza", "fatiga", "tos", "dolor de garganta", "mareos",
    ]
    first_person_patterns = [
        " i ", " i'm", "i am", " my ", " me ",
        "je ", " j'ai", " j ai", " mon ", " ma ", " mes ",
        "yo ", " tengo", " me siento", " mi ",
    ]

    symptom_hits = sum(1 for pattern in symptom_patterns if pattern in text)
    padded_text = f" {text} "
    first_person_hits = sum(1 for pattern in first_person_patterns if pattern in padded_text)
    return symptom_hits >= 2 and first_person_hits >= 1


def get_no_context_message(question: str) -> str:
    language = detect_question_language(question)
    if is_personal_symptom_question(question):
        return SYMPTOM_FALLBACK_MESSAGES.get(language, SYMPTOM_FALLBACK_MESSAGES["en"])
    return FALLBACK_MESSAGES.get(language, FALLBACK_MESSAGES["en"])


def build_learner_instruction(learner_profile: str | None = None) -> str:
    profile = (learner_profile or DEFAULT_LEARNER_PROFILE).strip()
    if not profile:
        return ""
    return (
        "Adapt the explanation depth to this learner profile: "
        f"{profile}. Keep explanations practical, structured, and clear for that level."
    )


def keyword_tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(token) > 2]


def strip_source_metadata(context: str) -> str:
    blocks = re.split(r"\n\s*\n", context or "")
    cleaned_blocks = []

    for block in blocks:
        chunk = block.strip()
        if not chunk:
            continue
        if "Content:" in chunk:
            chunk = chunk.split("Content:", 1)[1].strip()
        chunk = re.sub(r"(?im)^source:\s*.*$", "", chunk)
        chunk = re.sub(r"(?im)^url:\s*.*$", "", chunk)
        chunk = re.sub(r"\s+", " ", chunk).strip()
        if chunk:
            cleaned_blocks.append(chunk)

    return "\n\n".join(cleaned_blocks).strip()


def build_structured_fallback_answer(context: str, question: str) -> str:
    raw_context = strip_source_metadata(context)
    text = re.sub(r"\s+", " ", raw_context or context or "").strip()
    if not text:
        return get_no_context_message(question)

    language = detect_question_language(question)
    question_tokens = set(keyword_tokens(question))
    generic_tokens = {
        "what", "cause", "causes", "how", "why", "medical", "health", "with",
        "about", "from", "that", "this", "have", "been", "your",
    }
    question_tokens = {token for token in question_tokens if token not in generic_tokens}

    sentences = re.split(r"(?<=[.!?])\s+", text)
    scored = []

    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 35:
            continue
        sentence_tokens = set(keyword_tokens(sentence))
        score = len(question_tokens & sentence_tokens)
        if any(word in sentence.lower() for word in ("cause", "causes", "trigger", "blocked", "hormone", "bacteria")):
            score += 1
        scored.append((score, sentence))

    if not scored:
        return text[:600].rstrip(" ,;:")

    scored.sort(key=lambda item: (item[0], len(item[1])), reverse=True)
    top_sentences = []
    seen = set()
    for _, sentence in scored:
        if sentence in seen:
            continue
        seen.add(sentence)
        top_sentences.append(sentence)
        if len(top_sentences) >= 4:
            break

    if language == "fr":
        header_1 = "Reponse rapide:"
        header_2 = "Points essentiels:"
    elif language == "es":
        header_1 = "Respuesta rapida:"
        header_2 = "Puntos clave:"
    else:
        header_1 = "Quick answer:"
        header_2 = "Key points:"

    first = top_sentences[0]
    others = top_sentences[1:4]
    lines = [header_1, f"- {first}"]
    if others:
        lines.extend(["", header_2])
        for sentence in others:
            lines.append(f"- {sentence}")
    return "\n".join(lines).strip()


def build_fallback_answer(context: str, question: str) -> str:
    text = re.sub(r"\s+", " ", context or "").strip()
    language = detect_question_language(question)
    if not text:
        return FALLBACK_MESSAGES.get(language, FALLBACK_MESSAGES["en"])

    if "Source:" in context and "Content:" in context:
        return build_structured_fallback_answer(context, question)

    sentences = re.split(r"(?<=[.!?])\s+", text)
    selected = []
    current_length = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 25:
            continue
        selected.append(sentence)
        current_length += len(sentence)
        if len(selected) >= 3 or current_length >= 420:
            break

    summary = " ".join(selected).strip()
    if summary:
        return summary
    return text[:420].rstrip(" ,;:")


def format_generated_answer(answer: str) -> str:
    text = (answer or "").strip()
    if not text:
        return ""

    text = re.sub(r"[\u00a0\u2000-\u200a\u202f\u205f\u3000]", " ", text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^\)]+)\)", r"\1", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\((?:[a-z0-9-]+\.)+[a-z]{2,}\)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^###\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^##\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^#\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"(?m)^\s*---+\s*$", "", text)
    text = re.sub(r"(?im)^\s*sources?\s*:\s*.*$", "", text)
    text = re.sub(r"(?im)^\s*source\s*:\s*.*$", "", text)
    text = re.sub(
        r"(?im)^.*(?:references are listed|references listed|sources are listed separately|les references sont listees|les sources sont affichees).*$",
        "",
        text,
    )
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_history(history: list[dict] | None) -> list[dict]:
    safe_history = []
    for message in history or []:
        role = message.get("role", "")
        content = (message.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        safe_history.append({"role": role, "content": content})
    return safe_history[-MAX_HISTORY_MESSAGES:]


def build_input_messages(
    question: str,
    context: str,
    history: list[dict] | None = None,
    learner_profile: str | None = None,
):
    language = detect_question_language(question)
    learner_instruction = build_learner_instruction(learner_profile)
    system_prompt = f"{SYSTEM_PROMPT}\n{LANGUAGE_INSTRUCTIONS.get(language, LANGUAGE_INSTRUCTIONS['en'])}"
    if learner_instruction:
        system_prompt = f"{system_prompt}\n{learner_instruction}"
    messages = [{"role": "system", "content": system_prompt}]

    for item in normalize_history(history):
        messages.append({"role": item["role"], "content": item["content"]})

    messages.append(
        {
            "role": "user",
            "content": f"""Latest question:
{question}

Trusted medical context:
{context}

Write a concise, structured, and useful answer based only on this context.
If the context is not enough, say that briefly.
Do not include raw URLs or inline citations in the answer body.""",
        }
    )
    return messages


def build_web_messages(
    question: str,
    history: list[dict] | None = None,
    language_hint: str | None = None,
    learner_profile: str | None = None,
):
    language = language_hint or detect_question_language(question)
    learner_instruction = build_learner_instruction(learner_profile)
    system_prompt = f"{WEB_SYSTEM_PROMPT}\n{LANGUAGE_INSTRUCTIONS.get(language, LANGUAGE_INSTRUCTIONS['en'])}"
    if learner_instruction:
        system_prompt = f"{system_prompt}\n{learner_instruction}"
    messages = [{"role": "system", "content": system_prompt}]

    for item in normalize_history(history):
        messages.append({"role": item["role"], "content": item["content"]})

    messages.append(
        {
            "role": "user",
            "content": f"""Please search the web for trustworthy medical sources and answer this question:
{question}

Prefer sources such as WHO, CDC, NHS, or MedlinePlus when available.
Keep the answer concise and structured.
Do not include raw URLs or inline citations in the answer body.
Let the tool output provide the sources separately.""",
        }
    )
    return messages


def extract_response_payload(response) -> dict:
    if hasattr(response, "model_dump"):
        return response.model_dump()
    if hasattr(response, "dict"):
        return response.dict()
    return {}


def collect_sources(node, found: dict):
    if isinstance(node, dict):
        url = node.get("url")
        if isinstance(url, str) and url:
            found[url] = {
                "title": node.get("title", "") or node.get("label", "") or "Web source",
                "source": node.get("source", "") or "OpenAI Web Search",
                "url": url,
            }
        for value in node.values():
            collect_sources(value, found)
    elif isinstance(node, list):
        for item in node:
            collect_sources(item, found)


def extract_sources_from_response(response) -> list[dict]:
    payload = extract_response_payload(response)
    found = {}
    collect_sources(payload, found)
    return list(found.values())[:6]


def extract_urls_from_text(text: str) -> list[dict]:
    urls = []
    seen = set()
    for url in re.findall(r"https?://[^\s)\]>]+", text or ""):
        clean_url = url.rstrip(".,);]")
        if clean_url in seen:
            continue
        seen.add(clean_url)
        urls.append(
            {
                "title": "Web source",
                "source": "OpenAI Web Search",
                "url": clean_url,
            }
        )
    return urls[:6]


def extract_sources_from_chat_message(message) -> list[dict]:
    annotations = getattr(message, "annotations", None) or []
    found = {}

    for annotation in annotations:
        data = annotation
        if hasattr(annotation, "model_dump"):
            data = annotation.model_dump()
        citation = data.get("url_citation", {}) if isinstance(data, dict) else {}
        url = citation.get("url", "")
        if not url:
            continue
        found[url] = {
            "title": citation.get("title", "") or "Web source",
            "source": "OpenAI Web Search",
            "url": url,
        }

    return list(found.values())[:6]


def generate_answer(
    question: str,
    context: str,
    history: list[dict] | None = None,
    learner_profile: str | None = None,
) -> tuple[str, bool]:
    if not context.strip():
        return get_no_context_message(question), False

    client = get_client()
    if client is None:
        return build_fallback_answer(context, question), False

    try:
        if not USE_AZURE_OPENAI:
            response = client.responses.create(
                model=MODEL,
                input=build_input_messages(question, context, history=history, learner_profile=learner_profile),
            )
            answer = format_generated_answer(response.output_text or "")
            if answer:
                return answer, True
    except Exception as exc:
        logger.warning("Responses API answer generation failed for question=%r error=%s", question, exc)

    try:
        completion = client.chat.completions.create(
            model=MODEL,
            messages=build_input_messages(question, context, history=history, learner_profile=learner_profile),
        )
        answer = format_generated_answer(completion.choices[0].message.content or "")
        if answer:
            return answer, True
    except Exception as exc:
        logger.warning("Chat Completions answer generation failed for question=%r model=%s error=%s", question, MODEL, exc)

    return build_fallback_answer(context, question), False


def generate_web_answer(
    question: str,
    history: list[dict] | None = None,
    *,
    search_query: str | None = None,
    language_hint: str | None = None,
    learner_profile: str | None = None,
) -> tuple[str, bool, list[dict]]:
    client = get_client()
    if client is None:
        return "", False, []

    if USE_AZURE_OPENAI:
        logger.info("Azure OpenAI detected: skipping tool-based web search and using trusted web fallback.")
        return "", False, []

    query_for_search = search_query or question
    answer_language = language_hint or detect_question_language(question)

    try:
        response = client.responses.create(
            model=MODEL,
            tools=[
                {
                    "type": "web_search",
                    "filters": {
                        "allowed_domains": WEB_ALLOWED_DOMAINS,
                    },
                }
            ],
            tool_choice="auto",
            include=["web_search_call.action.sources"],
            input=build_web_messages(
                query_for_search,
                history=history,
                language_hint=answer_language,
                learner_profile=learner_profile,
            ),
        )
        answer = format_generated_answer(response.output_text or "")
        sources = extract_sources_from_response(response)
        if answer:
            return answer, True, sources
    except Exception as exc:
        logger.warning(
            "Responses API web_search failed for question=%r search_query=%r error=%s",
            question,
            query_for_search,
            exc,
        )

    try:
        completion = client.chat.completions.create(
            model=WEB_SEARCH_MODEL,
            web_search_options={},
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"{WEB_SYSTEM_PROMPT}\n"
                        f"{LANGUAGE_INSTRUCTIONS.get(answer_language, LANGUAGE_INSTRUCTIONS['en'])}\n"
                        f"{build_learner_instruction(learner_profile)}"
                    ),
                },
                {
                    "role": "user",
                    "content": query_for_search,
                },
            ],
        )
        message = completion.choices[0].message
        raw_content = message.content or ""
        answer = format_generated_answer(raw_content)
        sources = extract_sources_from_chat_message(message)
        if not sources:
            sources = extract_urls_from_text(raw_content)
        if answer:
            return answer, True, sources
    except Exception as exc:
        logger.warning(
            "Chat Completions web search fallback failed for question=%r search_query=%r model=%s error=%s",
            question,
            query_for_search,
            WEB_SEARCH_MODEL,
            exc,
        )

    return "", False, []
