"""Recommendation quality evaluation for Project NOVA - IntelliDesk."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app, db
from app.models import Category, KnowledgeArticle, User
from app.services.similar_tickets import find_similar_tickets
from app.services.knowledge_recommendations import (
    recommend_knowledge_articles,
)


# ============================================================
# TEST UTILITIES
# ============================================================

def make_ticket(
    ticket_id,
    title,
    description,
    status="open",
    days_old=0,
):
    """Create an in-memory ticket-like object for service evaluation."""
    return SimpleNamespace(
        id=ticket_id,
        title=title,
        description=description,
        status=status,
        created_at=(
            datetime.now(timezone.utc)
            - timedelta(days=days_old)
        ),
    )


def article_titles(recommendations):
    """Extract article titles from recommendation results."""
    return [
        item["article"].title
        for item in recommendations
    ]


def print_result(label, passed=True):
    status = "PASS" if passed else "FAIL"
    print(f"{label}: {status}")


def assert_top_article(query_title, query_description, expected_title):
    """Check whether the expected article ranks first."""
    results = recommend_knowledge_articles(
        query_title,
        query_description,
        limit=3,
        min_similarity=0.08,
    )

    titles = article_titles(results)

    assert titles, (
        f"No articles recommended for: {query_title}"
    )

    assert titles[0] == expected_title, (
        f"Expected '{expected_title}' at rank 1 for "
        f"'{query_title}', got: {titles}"
    )

    print(
        f"PASS: {query_title} -> {titles[0]} "
        f"({results[0]['similarity_percent']}%)"
    )

    return results


# ============================================================
# SIMILAR TICKET EVALUATION
# ============================================================

def evaluate_similar_tickets():
    print("\n========== SIMILAR TICKET EVALUATION ==========")

    candidates = [
        make_ticket(
            101,
            "Office Wi-Fi keeps disconnecting",
            (
                "Laptop repeatedly loses wireless network connection. "
                "Wi-Fi disconnects every few minutes."
            ),
            days_old=1,
        ),
        make_ticket(
            102,
            "Wireless network connection unstable",
            (
                "The laptop loses Wi-Fi connectivity and disconnects "
                "from the office network."
            ),
            days_old=2,
        ),
        make_ticket(
            103,
            "Unable to connect to office Wi-Fi",
            (
                "Wireless internet connection fails after connecting. "
                "Network keeps dropping."
            ),
            days_old=3,
        ),
        make_ticket(
            104,
            "Printer toner replacement",
            (
                "The office printer has low toner and needs a "
                "replacement cartridge."
            ),
            days_old=4,
        ),
        make_ticket(
            105,
            "Email inbox synchronization problem",
            (
                "Outlook inbox is not synchronizing incoming "
                "email messages."
            ),
            days_old=5,
        ),
        make_ticket(
            106,
            "Closed Wi-Fi issue",
            (
                "Office Wi-Fi keeps disconnecting from the network."
            ),
            status="closed",
            days_old=1,
        ),
    ]

    query_title = "Office Wi-Fi disconnecting repeatedly"
    query_description = (
        "My laptop keeps losing the wireless network connection. "
        "The Wi-Fi disconnects every few minutes."
    )

    results = find_similar_tickets(
        query_title,
        query_description,
        candidates,
        limit=3,
        min_similarity=0.10,
    )

    result_ids = [
        item["ticket"].id
        for item in results
    ]

    # 1. Relevant tickets should be returned.
    assert results, "No similar tickets were returned."
    print_result("1. Similar tickets are returned")

    # 2. The strongest match should rank first.
    assert result_ids[0] == 101, (
        f"Expected ticket 101 first, got {result_ids}"
    )
    print_result("2. Strongest matching ticket ranks first")

    # 3. The top results should be relevant network tickets.
    assert set(result_ids).issubset({101, 102, 103}), (
        f"Unexpected unrelated recommendation: {result_ids}"
    )
    print_result("3. Unrelated tickets excluded from top results")

    # 4. Closed tickets must never appear.
    assert 106 not in result_ids
    print_result("4. Closed tickets excluded")

    # 5. Recommendation count must respect the limit.
    assert len(results) <= 3
    print_result("5. Maximum three recommendations enforced")

    # 6. Explicit ticket exclusion must work.
    excluded_results = find_similar_tickets(
        query_title,
        query_description,
        candidates,
        exclude_ticket_id=101,
        limit=3,
        min_similarity=0.10,
    )

    excluded_ids = [
        item["ticket"].id
        for item in excluded_results
    ]

    assert 101 not in excluded_ids
    print_result("6. Explicit ticket exclusion works")

    # 7. An unrelated query must not recommend these tickets.
    unrelated_results = find_similar_tickets(
        "Request for office printer toner",
        "The printer needs a new toner cartridge.",
        candidates,
        limit=3,
        min_similarity=0.10,
    )

    unrelated_ids = [
        item["ticket"].id
        for item in unrelated_results
    ]

    assert not ({101, 102, 103} & set(unrelated_ids)), (
        f"Wi-Fi tickets incorrectly recommended: {unrelated_ids}"
    )
    print_result("7. Unrelated query avoids Wi-Fi recommendations")

    # 8. Empty query should return no recommendations.
    empty_results = find_similar_tickets(
        "",
        "",
        candidates,
    )

    assert empty_results == []
    print_result("8. Empty query handled safely")

    # 9. Empty candidate collection should return no results.
    no_candidate_results = find_similar_tickets(
        query_title,
        query_description,
        [],
    )

    assert no_candidate_results == []
    print_result("9. Empty candidate collection handled safely")

    # 10. Invalid recommendation limit should return no results.
    invalid_limit_results = find_similar_tickets(
        query_title,
        query_description,
        candidates,
        limit=0,
    )

    assert invalid_limit_results == []
    print_result("10. Invalid recommendation limit handled")

    print("\nSimilar-ticket ranking:")
    for rank, item in enumerate(results, start=1):
        ticket = item["ticket"]
        print(
            f"  {rank}. Ticket #{ticket.id}: {ticket.title} "
            f"({item['similarity_percent']}%)"
        )

    return 10


# ============================================================
# KNOWLEDGE BASE EVALUATION
# ============================================================

def evaluate_knowledge_recommendations():
    print("\n========== KNOWLEDGE BASE EVALUATION ==========")

    expected_articles = {
        "network": "Troubleshooting Wi-Fi and Network Connectivity",
        "software": (
            "Troubleshooting Windows Applications That Freeze or Crash"
        ),
        "hardware": (
            "Resolving Laptop and Desktop Hardware Problems"
        ),
        "account": (
            "Troubleshooting Account Login and Password Issues"
        ),
        "email": (
            "Resolving Email Sending and Receiving Problems"
        ),
    }

    # Confirm that the seeded articles exist and are published.
    for article_name in expected_articles.values():
        article = KnowledgeArticle.query.filter_by(
            title=article_name,
            is_published=True,
        ).first()

        assert article is not None, (
            f"Required published article missing: {article_name}"
        )

    print_result("1. Five expected published articles are available")

    # 2-6. Evaluate the five main IT categories.
    assert_top_article(
        "Wi-Fi keeps disconnecting",
        (
            "The laptop cannot maintain a wireless internet connection. "
            "The office network keeps dropping."
        ),
        expected_articles["network"],
    )

    assert_top_article(
        "Cannot log into Windows account",
        (
            "My account password is rejected and I cannot access "
            "my account. Authentication keeps failing."
        ),
        expected_articles["account"],
    )

    assert_top_article(
        "Outlook email not sending",
        (
            "Emails remain stuck in the outbox and incoming messages "
            "are not appearing in the inbox."
        ),
        expected_articles["email"],
    )

    assert_top_article(
        "Laptop overheating and shutting down",
        (
            "My computer gets very hot, the battery drains quickly, "
            "and the laptop shuts down unexpectedly."
        ),
        expected_articles["hardware"],
    )

    assert_top_article(
        "Windows application keeps freezing",
        (
            "The software application becomes unresponsive and "
            "crashes whenever I open it."
        ),
        expected_articles["software"],
    )

    # 7. Top-three recommendation limit.
    limited_results = recommend_knowledge_articles(
        "Computer problem",
        "My computer has an issue and needs troubleshooting.",
        limit=3,
        min_similarity=0.0,
    )

    assert len(limited_results) <= 3
    print_result("7. Knowledge recommendations respect top-three limit")

    # 8. Empty query should return no results.
    empty_results = recommend_knowledge_articles(
        "",
        "",
    )

    assert empty_results == []
    print_result("8. Empty Knowledge Base query handled safely")

    # 9. Invalid limit should return no results.
    invalid_results = recommend_knowledge_articles(
        "Wi-Fi problem",
        "Wireless network disconnecting.",
        limit=0,
    )

    assert invalid_results == []
    print_result("9. Invalid Knowledge Base limit handled")

    # 10. Draft articles must never be recommended.
    draft = KnowledgeArticle.query.filter_by(
        is_published=False
    ).first()

    if draft is not None:
        draft_query = recommend_knowledge_articles(
            draft.title,
            draft.summary + " " + draft.content,
            limit=10,
            min_similarity=0.0,
        )

        draft_ids = {
            item["article"].id
            for item in draft_query
        }

        assert draft.id not in draft_ids

    print_result(
        "10. Unpublished articles excluded from recommendations"
    )

    # Print the recommendations for a representative query.
    results = recommend_knowledge_articles(
        "Wi-Fi keeps disconnecting",
        (
            "The laptop cannot maintain a wireless internet connection. "
            "The office network keeps dropping."
        ),
        limit=3,
        min_similarity=0.08,
    )

    print("\nKnowledge Base ranking for Wi-Fi query:")
    for rank, item in enumerate(results, start=1):
        print(
            f"  {rank}. {item['article'].title} "
            f"({item['similarity_percent']}%)"
        )

    return 10


# ============================================================
# MAIN
# ============================================================

def run_tests():
    app = create_app()

    with app.app_context():

        # Safety check: do not run against another database.
        database_name = db.engine.url.database

        if database_name != "intellidesk":
            raise RuntimeError(
                "Database safety check failed. Expected 'intellidesk', "
                f"found {database_name!r}. No test data was changed."
            )

        print("Database safety check: PASS")
        print(f"Database: {database_name}")

        # Confirm the five seeded categories exist.
        expected_categories = {
            "Hardware",
            "Software",
            "Network",
            "Account Access",
            "Email & Communication",
        }

        actual_categories = {
            category.name
            for category in Category.query.all()
        }

        missing_categories = expected_categories - actual_categories

        if missing_categories:
            raise RuntimeError(
                "Required categories are missing: "
                + ", ".join(sorted(missing_categories))
            )

        print("Category availability check: PASS")

        similar_count = evaluate_similar_tickets()
        knowledge_count = evaluate_knowledge_recommendations()

        print("\n========== EVALUATION SUMMARY ==========")
        print(f"Similar-ticket checks: {similar_count}/{similar_count}")
        print(f"Knowledge Base checks: {knowledge_count}/{knowledge_count}")
        print(
            f"Total checks: "
            f"{similar_count + knowledge_count}/"
            f"{similar_count + knowledge_count}"
        )

        print("\nRECOMMENDATION QUALITY EVALUATION COMPLETED.")


if __name__ == "__main__":
    run_tests()
