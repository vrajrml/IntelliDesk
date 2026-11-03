"""Recommend relevant published Knowledge Base articles for tickets."""

import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.models import KnowledgeArticle


MAX_ARTICLES_TO_COMPARE = 2000
MAX_RECOMMENDATIONS = 3

# Reject weak matches by default. This is a ranking threshold,
# not a probability that an article will solve the problem.
MIN_SIMILARITY = 0.08

# Common IT vocabulary mapped to normalized concepts.
TERM_GROUPS = {
    "network": {
        "wifi", "wi-fi", "wireless", "internet", "network",
        "router", "connectivity", "connection", "disconnect",
        "disconnecting", "disconnected", "drops", "dropping",
        "offline", "ethernet", "lan",
    },
    "account": {
        "account", "login", "log-in", "signin", "sign-in",
        "password", "credentials", "authentication", "access",
        "locked", "lockout", "unlock",
    },
    "email": {
        "email", "emails", "mail", "outlook", "inbox",
        "outbox", "sending", "receiving", "smtp",
    },
    "hardware": {
        "laptop", "desktop", "computer", "pc", "hardware",
        "overheating", "overheat", "hot", "shutdown",
        "shutting", "battery", "keyboard", "screen", "printer",
    },
    "software": {
        "software", "application", "applications", "app",
        "apps", "program", "programs", "crash", "crashes",
        "crashing", "freeze", "freezes", "freezing",
        "hang", "hanging", "slow", "unresponsive",
    },
}

TERM_TO_CONCEPT = {
    term: concept
    for concept, terms in TERM_GROUPS.items()
    for term in terms
}

# Broad category labels used only to provide a modest ranking boost.
CATEGORY_CONCEPTS = {
    "network": {"network"},
    "account access": {"account"},
    "email & communication": {"email"},
    "hardware": {"hardware"},
    "software": {"software"},
}


def _normalize_text(text):
    """Normalize common IT vocabulary while preserving original words."""
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    normalized = []

    for token in tokens:
        normalized.append(token)

        concept = TERM_TO_CONCEPT.get(token)
        if concept:
            normalized.append(concept)

    return " ".join(normalized)


def _build_article_text(article):
    """Combine article fields into searchable text."""
    parts = (
        article.title,
        article.summary,
        article.content,
        article.category.name if article.category else "",
    )

    return " ".join(part for part in parts if part)


def _query_concepts(text):
    """Return normalized IT concepts found in text."""
    concepts = set()

    for token in re.findall(r"[a-z0-9]+", (text or "").lower()):
        concept = TERM_TO_CONCEPT.get(token)

        if concept:
            concepts.add(concept)

    return concepts


def recommend_knowledge_articles(
    title,
    description,
    limit=MAX_RECOMMENDATIONS,
    min_similarity=MIN_SIMILARITY,
    category_id=None,
):
    """
    Return relevant published articles ranked by textual similarity.

    A small category relevance boost can be applied when category_id
    is provided. Only published articles are considered.

    Returns dictionaries containing:
        article: KnowledgeArticle
        similarity_percent: integer percentage
    """
    title = (title or "").strip()
    description = (description or "").strip()

    if not title and not description:
        return []

    if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
        return []

    if not 0 <= min_similarity <= 1:
        raise ValueError("min_similarity must be between 0 and 1.")

    articles = (
        KnowledgeArticle.query
        .filter_by(is_published=True)
        .order_by(KnowledgeArticle.updated_at.desc())
        .limit(MAX_ARTICLES_TO_COMPARE)
        .all()
    )

    if not articles:
        return []

    weighted_query = _normalize_text(
        f"{title} {title} {description}"
    )

    article_texts = [
        _normalize_text(_build_article_text(article))
        for article in articles
    ]

    documents = article_texts + [weighted_query]

    try:
        vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 2),
            max_features=20000,
            sublinear_tf=True,
        )

        matrix = vectorizer.fit_transform(documents)

    except ValueError:
        return []

    scores = cosine_similarity(
        matrix[-1:],
        matrix[:-1],
    ).flatten()

    query_concepts = _query_concepts(
        f"{title} {description}"
    )

    ranked = []

    for index, article in enumerate(articles):
        raw_score = float(scores[index])

        if raw_score <= 0:
            continue

        article_category = (
            (article.category.name or "").strip().lower()
            if article.category
            else ""
        )

        expected_concepts = CATEGORY_CONCEPTS.get(
            article_category,
            set(),
        )

        category_boost = 0.0

        # Give a modest preference to articles whose category matches
        # concepts explicitly present in the ticket text.
        if expected_concepts & query_concepts:
            category_boost = 0.04

        adjusted_score = min(
            raw_score + category_boost,
            1.0,
        )

        if adjusted_score < min_similarity:
            continue

        ranked.append(
            {
                "article": article,
                "score": adjusted_score,
            }
        )

    ranked.sort(
        key=lambda item: (
            item["score"],
            item["article"].updated_at,
            item["article"].id,
        ),
        reverse=True,
    )

    return [
        {
            "article": item["article"],
            "similarity_percent": round(item["score"] * 100),
        }
        for item in ranked[:limit]
    ]