import re
from collections import Counter

import chromadb
from chromadb.utils import embedding_functions

CHROMA_DB_PATH = "chatbot/chroma_db"
COLLECTION_NAME = "medical_chunks"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

TOPIC_MAP = {
    "acne": ["acne", "acne scar", "acne scars", "pimples"],
    "covid": ["covid", "covid-19", "corona", "coronavirus", "sars-cov-2"],
    "asthma": ["asthma"],
    "diabetes": ["diabetes", "glucose", "blood sugar"],
    "flu": ["flu", "influenza"],
    "heart": ["heart disease", "heart", "cardiac"],
    "stroke": ["stroke"],
    "obesity": ["obesity", "overweight"],
    "pneumonia": ["pneumonia"],
    "arthritis": ["arthritis"],
    "kidney": ["kidney", "renal"],
    "lung_cancer": ["lung cancer"],
    "lung": ["lung disease", "lung diseases"],
    "bloodpressure": ["blood pressure", "high blood pressure", "hypertension"],
}

SECTION_HINTS = {
    "symptoms": ["symptom", "symptoms", "sign", "signs"],
    "causes": ["cause", "causes", "caused by", "why", "trigger", "spread", "risk factor"],
    "prevention": ["prevent", "prevention", "avoid", "protect", "vaccine", "vaccination"],
    "treatment": ["treat", "treatment", "therapy", "medicine", "medication", "manage"],
    "definition": ["what is", "define", "definition", "overview"],
}

STOPWORDS = {
    "about", "after", "also", "and", "are", "can", "for", "from", "how", "into",
    "its", "many", "more", "that", "than", "the", "their", "them", "they", "this",
    "was", "what", "when", "where", "which", "while", "who", "will", "with", "would",
    "your",
}

INTENT_TOKENS = {
    "cause", "causes", "caused", "symptom", "symptoms", "sign", "signs", "prevent",
    "prevention", "avoid", "protect", "vaccine", "vaccination", "treat", "treatment",
    "therapy", "therapies", "medicine", "medication", "manage", "definition", "define",
    "overview", "disease", "diseases", "condition", "conditions", "medical", "health",
    "means", "meaning",
}


def get_plain_collection():
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    return client.get_collection(name=COLLECTION_NAME)


def get_collection():
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL_NAME,
        local_files_only=True,
    )
    return chromadb.PersistentClient(path=CHROMA_DB_PATH).get_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn
    )


def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def detect_main_topic(question: str) -> str:
    q = question.lower()
    for topic, keywords in TOPIC_MAP.items():
        if any(keyword in q for keyword in keywords):
            return topic
    return ""


def detect_target_section(question: str) -> str:
    q = question.lower()
    for section, keywords in SECTION_HINTS.items():
        if any(keyword in q for keyword in keywords):
            return section
    return ""


def extract_content(chunk_text: str) -> str:
    text = chunk_text or ""
    if "Content:" in text:
        text = text.split("Content:", 1)[1]
    if "URL:" in text:
        text = text.split("URL:", 1)[0]
    text = clean_text(text)
    noise_patterns = [
        r"On this page.*?Summary",
        r"Start Here Symptoms Diagnosis and Tests Prevention and Risk Factors Treatments and Therapies",
        r"Start Here Diagnosis and Tests Prevention and Risk Factors Treatments and Therapies",
        r"Learn More Related Issues Specifics See, Play and Learn",
        r"Learn More Related Issues Specifics",
        r"Learn More Living With Related Issues",
        r"No links available Research Statistics and Research",
        r"Images Videos and Tutorials Test Your Knowledge",
        r"Find an Expert For You Children Women Older Adults Patient Handouts",
    ]
    for pattern in noise_patterns:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    return clean_text(text)


def tokenize(text: str):
    tokens = re.findall(r"[a-z0-9-]+", (text or "").lower())
    return [token for token in tokens if len(token) > 2 and token not in STOPWORDS]


def extract_subject_tokens(question: str) -> list[str]:
    return [token for token in tokenize(question) if token not in INTENT_TOKENS]


def matches_topic(meta: dict, topic: str) -> bool:
    keywords = TOPIC_MAP.get(topic, [])
    if clean_text(meta.get("disease", "")).lower() == topic:
        return True
    title = clean_text(meta.get("title", "")).lower()
    url = clean_text(meta.get("url", "")).lower()
    return any(keyword in title or keyword in url for keyword in keywords)


def rank_pairs(question: str, pairs, n_results: int = 8):
    topic = detect_main_topic(question)
    target_section = detect_target_section(question)
    question_tokens = set(tokenize(question))
    subject_tokens = set(extract_subject_tokens(question))

    if topic:
        topic_pairs = [
            (doc, meta or {})
            for doc, meta in pairs
            if matches_topic(meta or {}, topic)
        ]
        if topic_pairs:
            pairs = topic_pairs
        else:
            return []

    ranked = []
    for doc, meta in pairs:
        meta = meta or {}
        content = extract_content(doc)
        if not content:
            continue
        searchable_text = " ".join([
            meta.get("title", ""),
            meta.get("section", ""),
            meta.get("url", ""),
            content,
        ])
        token_counts = Counter(tokenize(searchable_text))
        score = sum(token_counts[token] for token in question_tokens)
        subject_overlap = {token for token in subject_tokens if token in token_counts}

        if topic and matches_topic(meta, topic):
            score += 6
        if target_section and clean_text(meta.get("section", "")).lower() == target_section:
            score += 3
            score += sum(content.lower().count(keyword) for keyword in SECTION_HINTS[target_section])
        score += len(subject_overlap) * 4

        if score > 0:
            ranked.append((score, len(subject_overlap), doc, meta))

    if not ranked and topic:
        for doc, meta in pairs:
            meta = meta or {}
            if matches_topic(meta, topic):
                ranked.append((1, 1, doc, meta))

    if subject_tokens and not topic:
        ranked = [item for item in ranked if item[1] > 0]

    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [(doc, meta) for _, _, doc, meta in ranked[:n_results]]


def dedupe_pairs(pairs):
    unique_pairs = []
    seen = set()
    for doc, meta in pairs:
        meta = meta or {}
        content = extract_content(doc)
        key = (
            meta.get("title", ""),
            meta.get("section", ""),
            content,
        )
        if key in seen:
            continue
        seen.add(key)
        unique_pairs.append((doc, meta))
    return unique_pairs


def build_context(pairs, max_chunks: int = 3) -> str:
    contents = []
    seen = set()
    for doc, _ in dedupe_pairs(pairs):
        content = extract_content(doc)
        if not content or content in seen:
            continue
        seen.add(content)
        contents.append(content)
        if len(contents) >= max_chunks:
            break
    return "\n\n".join(contents).strip()


def retrieve_pairs_with_vector_search(question: str, n_results: int = 8):
    collection = get_collection()
    results = collection.query(
        query_texts=[question],
        n_results=n_results
    )
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    pairs = dedupe_pairs(list(zip(documents, metadatas)))
    return rank_pairs(question, pairs, n_results=n_results)


def retrieve_pairs_with_keyword_search(question: str, n_results: int = 8):
    collection = get_plain_collection()
    total = collection.count()
    if total == 0:
        return []

    results = collection.get(
        limit=total,
        include=["documents", "metadatas"]
    )
    documents = results.get("documents", [])
    metadatas = results.get("metadatas", [])
    pairs = dedupe_pairs(list(zip(documents, metadatas)))
    return rank_pairs(question, pairs, n_results=n_results)


def retrieve_local_context(question: str, n_results: int = 8):
    try:
        pairs = retrieve_pairs_with_vector_search(question, n_results=n_results)
    except Exception:
        pairs = []

    context = build_context(pairs)

    if len(context) < 120:
        try:
            keyword_pairs = retrieve_pairs_with_keyword_search(question, n_results=n_results)
        except Exception:
            keyword_pairs = []
        keyword_context = build_context(keyword_pairs)
        if len(keyword_context) > len(context):
            pairs = keyword_pairs
            context = keyword_context

    if not pairs:
        return {
            "mode": "local_rag",
            "context": "",
            "main_source": {},
            "other_sources": []
        }

    pairs = dedupe_pairs(pairs)
    best_meta = pairs[0][1] or {}
    main_source = {
        "title": best_meta.get("title", ""),
        "source": best_meta.get("source", ""),
        "url": best_meta.get("url", "")
    }
    other_sources = []
    seen = {(best_meta.get("title", ""), best_meta.get("url", ""))}
    for _, meta in pairs[1:]:
        meta = meta or {}
        key = (meta.get("title", ""), meta.get("url", ""))
        if key not in seen:
            seen.add(key)
            other_sources.append({
                "title": meta.get("title", ""),
                "source": meta.get("source", ""),
                "url": meta.get("url", "")
            })
        if len(other_sources) >= 2:
            break
    return {
        "mode": "local_rag",
        "context": context,
        "main_source": main_source,
        "other_sources": other_sources
    }


if __name__ == "__main__":
    print(retrieve_local_context("What causes COVID-19?"))
