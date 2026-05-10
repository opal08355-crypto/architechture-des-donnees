import re
import unicodedata
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from ddgs import DDGS

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

ALLOWED_DOMAINS = [
    "medlineplus.gov",
    "nhs.uk",
    "who.int",
    "cdc.gov",
    "mayoclinic.org",
    "nih.gov",
    "clevelandclinic.org",
    "msdmanuals.com",
]

DOMAIN_WEIGHTS = {
    "medlineplus.gov": 10,
    "nhs.uk": 9,
    "mayoclinic.org": 8,
    "clevelandclinic.org": 8,
    "msdmanuals.com": 7,
    "nih.gov": 6,
    "cdc.gov": 5,
    "who.int": 2,
}

GENERIC_QUERY_TOKENS = {
    "what", "causes", "cause", "medical", "health", "disease", "symptoms",
    "treatment", "treat", "prevent", "prevention", "how", "why", "with",
    "pour", "quel", "quelle", "quels", "quelles", "medicament", "medicaments",
    "medicine", "medication", "medications", "prendre", "prends", "take", "takes",
}

LOW_VALUE_PATH_HINTS = (
    "/search/results",
    "/nhs-services/",
    "/service-search/",
    "/search/",
    "/mega-menu/",
    "/emergencies/",
    "/countries/",
    "/country-office",
    "/news-room/",
)

HIGH_VALUE_PATH_HINTS = (
    "/conditions/",
    "/condition/",
    "/diseases-conditions/",
    "/symptoms-causes/",
    "/diagnosis-treatment/",
    "/article/",
    "/ency/",
)

CONDITION_ALIASES = {
    "hemorrhoids": {
        "hemorrhoids", "hemorrhoid", "haemorrhoids", "haemorrhoid",
        "hemorroides", "hemorroide", "hemorroid", "hermoides", "hemoroides", "piles",
    },
    "back pain": {
        "back pain", "backache", "mal de dos", "douleur dos", "douleur au dos", "dos",
    },
    "acne": {"acne", "pimples", "zit", "zits", "boutons"},
    "diabetes": {"diabetes", "diabete", "blood sugar", "glycemia", "glycemie"},
    "hypertension": {
        "hypertension", "high blood pressure", "blood pressure", "pression arterielle",
    },
}

INTENT_ALIASES = {
    "treatment": {
        "treatment", "treat", "therapy", "therapies", "manage", "management",
        "medication", "medicine", "medicines", "drugs", "drug", "relief",
        "traitement", "traiter", "gerer", "gestion", "medicament", "medicaments",
        "prendre", "prends", "soigner", "soulager",
    },
    "symptoms": {
        "symptoms", "symptom", "signs", "symptomes", "symptome", "signes",
    },
    "causes": {
        "causes", "cause", "why", "trigger", "caused", "pourquoi",
    },
    "prevention": {
        "prevent", "prevention", "avoid", "protection", "vaccination",
        "prevenir", "prevention", "eviter",
    },
}

INTENT_SEARCH_PHRASES = {
    "treatment": "treatment medication",
    "symptoms": "symptoms signs",
    "causes": "causes risk factors",
    "prevention": "prevention self care",
}

CONDITION_NEGATIVE_HINTS = {
    "hypertension": {"pulmonary", "intracranial", "pregnancy"},
}

CONDITION_PRIORITY_PHRASES = {
    "hypertension": {"high blood pressure", "blood pressure"},
    "hemorrhoids": {"piles", "haemorrhoids", "hemorrhoids"},
}

PROVIDER_SEARCH_URLS = [
    ("https://medlineplus.gov/search/?query={query}", "MedlinePlus"),
    ("https://www.nhs.uk/search/results?q={query}", "NHS"),
    ("https://search.cdc.gov/search/?query={query}", "CDC"),
    ("https://www.who.int/search?query={query}", "WHO"),
]


def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def ascii_normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


def split_words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", ascii_normalize(text))


def edit_distance_at_most(a: str, b: str, max_distance: int = 2) -> int:
    if a == b:
        return 0
    if abs(len(a) - len(b)) > max_distance:
        return max_distance + 1
    if not a or not b:
        return max(len(a), len(b))

    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current = [i]
        min_in_row = current[0]
        for j, char_b in enumerate(b, start=1):
            cost = 0 if char_a == char_b else 1
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + cost,
                )
            )
            if current[-1] < min_in_row:
                min_in_row = current[-1]
        if min_in_row > max_distance:
            return max_distance + 1
        previous = current
    return previous[-1]


def build_medical_vocabulary() -> set[str]:
    vocab = set()
    for aliases in CONDITION_ALIASES.values():
        for alias in aliases:
            for token in split_words(alias):
                if len(token) >= 4:
                    vocab.add(token)
    for aliases in INTENT_ALIASES.values():
        for alias in aliases:
            for token in split_words(alias):
                if len(token) >= 4:
                    vocab.add(token)
    return vocab


MEDICAL_VOCAB = build_medical_vocabulary()


def is_allowed_url(url: str) -> bool:
    url = (url or "").lower()
    return any(domain in url for domain in ALLOWED_DOMAINS)


def detect_domain(url: str) -> str:
    hostname = urlparse(url or "").netloc.lower()
    for domain in DOMAIN_WEIGHTS:
        if domain in hostname:
            return domain
    return hostname


def normalize_search_result_url(url: str) -> str:
    parsed = urlparse(url)
    if "/search/click" in parsed.path:
        params = parse_qs(parsed.query)
        target = params.get("url", [""])[0]
        if target:
            return urljoin(f"{parsed.scheme}://{parsed.netloc}", unquote(target))
    return url


def tokenize_query(text: str):
    normalized = ascii_normalize(text)
    return [
        token
        for token in re.findall(r"[a-z0-9]+", normalized)
        if len(token) > 2 and token not in GENERIC_QUERY_TOKENS
    ]


def normalize_query_spelling(query: str) -> str:
    raw_tokens = split_words(query)
    corrected_tokens = []

    for token in raw_tokens:
        if (
            len(token) < 5
            or token in GENERIC_QUERY_TOKENS
            or token in MEDICAL_VOCAB
            or token.isdigit()
        ):
            corrected_tokens.append(token)
            continue

        best_candidate = token
        best_distance = 3
        for candidate in MEDICAL_VOCAB:
            if candidate[0] != token[0]:
                continue
            distance = edit_distance_at_most(token, candidate, max_distance=2)
            if distance < best_distance:
                best_candidate = candidate
                best_distance = distance
                if distance == 1:
                    break
        corrected_tokens.append(best_candidate if best_distance <= 2 else token)

    return " ".join(corrected_tokens).strip()


def detect_condition(query: str) -> str:
    normalized_query = ascii_normalize(query)
    padded_query = f" {normalized_query} "
    tokens = set(tokenize_query(query))

    for canonical, aliases in CONDITION_ALIASES.items():
        for alias in aliases:
            alias_norm = ascii_normalize(alias)
            if alias_norm in tokens or f" {alias_norm} " in padded_query:
                return canonical
    return ""


def detect_intent(query: str) -> str:
    normalized_query = ascii_normalize(query)
    padded_query = f" {normalized_query} "
    tokens = set(tokenize_query(query))

    for intent, aliases in INTENT_ALIASES.items():
        for alias in aliases:
            alias_norm = ascii_normalize(alias)
            if alias_norm in tokens or f" {alias_norm} " in padded_query:
                return intent
    return ""


def build_query_profile(query: str) -> dict:
    corrected_query = normalize_query_spelling(query)
    detection_query = corrected_query or query

    condition = detect_condition(detection_query)
    intent = detect_intent(detection_query)
    tokens = tokenize_query(detection_query)
    canonical_tokens = tokenize_query(condition)

    search_candidates = [clean_text(query)]
    if corrected_query and ascii_normalize(corrected_query) != ascii_normalize(query):
        search_candidates.append(corrected_query)
    if condition and intent:
        search_candidates.append(f"{condition} {INTENT_SEARCH_PHRASES.get(intent, intent)}")
        search_candidates.append(f"{condition} {intent}")
    if condition:
        search_candidates.append(condition)
        for phrase in CONDITION_PRIORITY_PHRASES.get(condition, set()):
            search_candidates.append(f"{phrase} {INTENT_SEARCH_PHRASES.get(intent, 'medical')}")

    deduped_candidates = []
    seen = set()
    for candidate in search_candidates:
        normalized = ascii_normalize(candidate)
        if not candidate or normalized in seen:
            continue
        seen.add(normalized)
        deduped_candidates.append(candidate)

    return {
        "original_query": clean_text(query),
        "normalized_query": corrected_query,
        "condition": condition,
        "intent": intent,
        "tokens": tokens,
        "normalized_tokens": set(tokens),
        "canonical_tokens": canonical_tokens,
        "condition_aliases": CONDITION_ALIASES.get(condition, set()),
        "search_candidates": deduped_candidates,
    }


def score_result_for_query(title: str, url: str, query_profile: dict) -> int:
    title_text = ascii_normalize(title or "")
    url_text = ascii_normalize(url or "")
    domain = detect_domain(url)

    score = DOMAIN_WEIGHTS.get(domain, 0)

    tokens = set(query_profile.get("tokens", []))
    canonical_tokens = set(query_profile.get("canonical_tokens", []))
    condition = query_profile.get("condition", "")
    intent = query_profile.get("intent", "")
    normalized_tokens = set(query_profile.get("normalized_tokens", set()))

    title_score = sum(1 for token in tokens if token in title_text)
    url_score = sum(1 for token in tokens if token in url_text)
    score += (title_score * 4) + (url_score * 3)

    if canonical_tokens:
        score += sum(4 for token in canonical_tokens if token in title_text)
        score += sum(3 for token in canonical_tokens if token in url_text)

    if condition:
        condition_text = ascii_normalize(condition)
        if condition_text in title_text:
            score += 6
        if condition_text.replace(" ", "-") in url_text or condition_text.replace(" ", "") in url_text:
            score += 5
        for phrase in CONDITION_PRIORITY_PHRASES.get(condition, set()):
            phrase_text = ascii_normalize(phrase)
            if phrase_text and (phrase_text in title_text or phrase_text in url_text):
                score += 5

    if any(hint in url_text for hint in HIGH_VALUE_PATH_HINTS):
        score += 4
    if any(hint in url_text for hint in LOW_VALUE_PATH_HINTS):
        score -= 8

    if domain == "who.int" and intent in {"treatment", "symptoms"}:
        score -= 6

    if intent == "treatment":
        if any(keyword in title_text for keyword in ("treatment", "treat", "manage", "relief", "diagnosis", "medication")):
            score += 5
        if any(keyword in url_text for keyword in ("treatment", "diagnosis-treatment", "manage", "haemorrhoids", "hemorrhoids")):
            score += 4
    elif intent == "symptoms":
        if "symptom" in title_text or "symptom" in url_text:
            score += 4
    elif intent == "causes":
        if "cause" in title_text or "cause" in url_text:
            score += 4
    elif intent == "prevention":
        if "prevent" in title_text or "prevent" in url_text:
            score += 4

    if title_text.startswith(("country office", "israel and occupied palestinian territory")):
        score -= 20

    # Penalize known off-topic variants for a detected condition when the query does not ask for them.
    negative_hints = CONDITION_NEGATIVE_HINTS.get(condition, set())
    for hint in negative_hints:
        if hint not in normalized_tokens and (hint in title_text or hint in url_text):
            score -= 8

    return score


def matches_condition(item: dict, query_profile: dict) -> bool:
    condition = query_profile.get("condition", "")
    if not condition:
        return True

    haystack = " ".join(
        [
            ascii_normalize(item.get("title", "")),
            ascii_normalize(item.get("url", "")),
            ascii_normalize(item.get("snippet", "")),
        ]
    )
    aliases = {ascii_normalize(alias) for alias in query_profile.get("condition_aliases", set())}
    aliases.update({ascii_normalize(condition), ascii_normalize(condition).replace(" ", "-")})
    has_condition_match = any(alias and alias in haystack for alias in aliases)
    if not has_condition_match:
        return False

    normalized_tokens = set(query_profile.get("normalized_tokens", set()))
    for hint in CONDITION_NEGATIVE_HINTS.get(condition, set()):
        if hint not in normalized_tokens and hint in haystack:
            return False
    return True


def parse_search_results_page(html: str, base_url: str, source_name: str, query_profile: dict, max_results: int = 6):
    soup = BeautifulSoup(html, "html.parser")
    ranked = []
    seen = set()

    for link in soup.find_all("a", href=True):
        href = urljoin(base_url, link.get("href", "")).strip()
        href = normalize_search_result_url(href)
        title = clean_text(link.get_text(" ", strip=True))
        if not href or not title or not is_allowed_url(href):
            continue
        if title.lower().startswith(("skip", "next", "here's how you know")):
            continue
        if "search.cdc.gov/search/" in href.lower() and "#" in href:
            continue
        if href.endswith("#"):
            continue
        if href.endswith("#main-content") or href.rstrip("/") in {"https://www.nhs.uk", "https://www.nhs.uk/"}:
            continue

        key = (title, href)
        if key in seen:
            continue
        seen.add(key)

        score = score_result_for_query(title, href, query_profile)
        if score <= 0:
            continue
        ranked.append(
            (
                score,
                {
                    "title": title,
                    "url": href,
                    "snippet": source_name,
                },
            )
        )
        if len(ranked) >= max_results * 4:
            break

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [item for _, item in ranked[:max_results]]


def search_trusted_site_pages(query: str, max_results: int = 6):
    session = requests.Session()
    session.trust_env = False
    profile = build_query_profile(query)

    aggregated = []
    seen = set()

    for candidate_query in profile["search_candidates"]:
        encoded_query = quote_plus(candidate_query)
        for template, source_name in PROVIDER_SEARCH_URLS:
            try:
                url = template.format(query=encoded_query)
                response = session.get(url, headers=HEADERS, timeout=20)
                if response.status_code != 200:
                    continue
                results = parse_search_results_page(
                    response.text,
                    url,
                    source_name,
                    query_profile=profile,
                    max_results=max_results,
                )
                for item in results:
                    key = (item["title"], item["url"])
                    if key in seen:
                        continue
                    seen.add(key)
                    aggregated.append(item)
            except Exception:
                continue

    return rank_links_for_question(query, aggregated, max_results=max_results)


def rank_links_for_question(query: str, links: list[dict], max_results: int = 6) -> list[dict]:
    profile = build_query_profile(query)
    ranked = []
    seen = set()

    for item in links:
        title = item.get("title", "")
        url = item.get("url", "")
        if not title or not url:
            continue
        key = (title, url)
        if key in seen:
            continue
        seen.add(key)
        if not matches_condition(item, profile):
            continue
        score = score_result_for_query(title, url, profile)
        if score <= 0:
            continue
        ranked.append((score, item))

    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in ranked[:max_results]]


def search_web_links(query: str, max_results: int = 6):
    profile = build_query_profile(query)
    results = []

    try:
        with DDGS() as ddgs:
            for candidate_query in profile["search_candidates"]:
                for item in ddgs.text(candidate_query, max_results=max_results):
                    href = item.get("href") or item.get("url") or ""
                    title = item.get("title", "")
                    body = item.get("body", "")
                    if href and is_allowed_url(href):
                        results.append(
                            {
                                "title": title,
                                "url": href,
                                "snippet": body,
                            }
                        )
    except Exception:
        return rank_links_for_question(query, search_trusted_site_pages(query, max_results=max_results), max_results=max_results)

    if not results:
        return rank_links_for_question(query, search_trusted_site_pages(query, max_results=max_results), max_results=max_results)
    return rank_links_for_question(query, results, max_results=max_results)


def extract_page_content(url: str) -> str:
    try:
        session = requests.Session()
        session.trust_env = False
        response = session.get(url, headers=HEADERS, timeout=20)
        if response.status_code != 200:
            return ""
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        paragraphs = soup.find_all("p")
        good = []
        for p in paragraphs:
            text = clean_text(p.get_text(" ", strip=True))
            text = re.sub(r"https?://\S+", "", text)
            text = re.sub(r"\bSCIENCE PHOTO LIBRARY\b", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s+", " ", text).strip()
            if len(text) > 80:
                good.append(text)
        return clean_text(" ".join(good[:6]))
    except Exception:
        return ""


def build_multi_source_context(question: str, links: list[dict], max_sources: int = 3) -> tuple[str, list[dict]]:
    selected_links = rank_links_for_question(question, links, max_results=max_sources)
    sections = []
    kept_sources = []

    for item in selected_links:
        content = extract_page_content(item["url"])
        if not content:
            content = clean_text(item.get("snippet", ""))
        if len(content) < 80:
            continue
        kept_sources.append(item)
        sections.append(
            f"Source: {item['title']}\nURL: {item['url']}\nContent: {content}"
        )

    return "\n\n".join(sections).strip(), kept_sources


def retrieve_web_context(question: str):
    links = search_web_links(question, max_results=6)
    if not links:
        links = search_web_links(f"{question} medical health", max_results=6)
    if not links:
        return {
            "mode": "web_search",
            "context": "",
            "main_source": {},
            "other_sources": [],
        }

    context, kept_sources = build_multi_source_context(question, links, max_sources=3)
    if not kept_sources:
        kept_sources = links[:3]
        main = kept_sources[0]
        context = extract_page_content(main["url"]) or main.get("snippet", "")
    else:
        main = kept_sources[0]

    main_source = {
        "title": main.get("title", ""),
        "source": "Web Search",
        "url": main.get("url", ""),
    }
    other_sources = []
    for item in kept_sources[1:3]:
        other_sources.append(
            {
                "title": item.get("title", ""),
                "source": "Web Search",
                "url": item.get("url", ""),
            }
        )
    return {
        "mode": "web_search",
        "context": context,
        "main_source": main_source,
        "other_sources": other_sources,
    }


if __name__ == "__main__":
    print(retrieve_web_context("What causes COVID-19?"))
