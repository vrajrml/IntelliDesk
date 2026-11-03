"""Find potentially related tickets using TF-IDF and cosine similarity."""

import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# Closed tickets are excluded from recommendations.
EXCLUDED_STATUSES = {"closed"}

# Only display matches with at least this much textual similarity.
DEFAULT_MIN_SIMILARITY = 0.10

# Avoid processing an unnecessarily large number of tickets at once.
DEFAULT_MAX_CANDIDATES = 2000


def _normalize_text(value):
    """Normalize text while retaining useful technical identifiers."""
    if not value:
        return ""

    text = str(value).lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def find_similar_tickets(
    title,
    description,
    candidates,
    *,
    exclude_ticket_id=None,
    limit=3,
    min_similarity=DEFAULT_MIN_SIMILARITY,
):
    """
    Rank existing tickets by textual similarity to a proposed ticket.

    Args:
        title: Proposed ticket title.
        description: Proposed ticket description.
        candidates: Iterable of existing Ticket objects.
        exclude_ticket_id: Optional ticket ID to exclude from results.
        limit: Maximum number of recommendations.
        min_similarity: Minimum cosine similarity, from 0 to 1.

    Returns:
        A list of dictionaries containing the matching ticket and its
        similarity score, sorted from highest to lowest.

    Notes:
        Similarity measures textual resemblance, not whether two tickets
        share the same underlying cause.
    """
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        return []

    if not 0 <= min_similarity <= 1:
        raise ValueError("min_similarity must be between 0 and 1.")

    proposed_title = _normalize_text(title)
    proposed_description = _normalize_text(description)
    proposed_text = f"{proposed_title} {proposed_description}".strip()

    if not proposed_text:
        return []

    eligible_tickets = []

    for ticket in candidates:
        if exclude_ticket_id is not None and ticket.id == exclude_ticket_id:
            continue

        if ticket.status in EXCLUDED_STATUSES:
            continue

        candidate_text = (
            f"{_normalize_text(ticket.title)} "
            f"{_normalize_text(ticket.description)}"
        ).strip()

        if candidate_text:
            eligible_tickets.append((ticket, candidate_text))

    if not eligible_tickets:
        return []

    # Keep the most recent candidates when the input exceeds the limit.
    # The route should normally pass candidates ordered newest first.
    eligible_tickets = eligible_tickets[:DEFAULT_MAX_CANDIDATES]

    documents = [
        proposed_text,
        *(text for _, text in eligible_tickets),
    ]

    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        max_features=20000,
        sublinear_tf=True,
    )

    try:
        matrix = vectorizer.fit_transform(documents)
    except ValueError:
        # For example, every document might contain only English stop words.
        return []

    scores = cosine_similarity(matrix[0:1], matrix[1:]).flatten()

    matches = []

    for (ticket, _), score in zip(eligible_tickets, scores):
        similarity = float(score)

        if similarity < min_similarity:
            continue

        matches.append(
            {
                "ticket": ticket,
                "similarity": similarity,
                "similarity_percent": round(similarity * 100, 1),
            }
        )

    matches.sort(
        key=lambda match: (
            match["similarity"],
            match["ticket"].created_at,
            match["ticket"].id,
        ),
        reverse=True,
    )

    return matches[:limit]
