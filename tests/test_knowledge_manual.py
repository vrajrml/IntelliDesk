"""Manual integration tests for the IntelliDesk Knowledge Base."""

import re
import sys
from pathlib import Path

from flask import g

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app, db
from app.models import Category, KnowledgeArticle, User
from app.routes.knowledge import generate_slug


TEST_PASSWORD = "NovaKnowledgePass123!"

TEST_USERS = {
    "user": "nova_kb_user",
    "technician": "nova_kb_technician",
    "other_technician": "nova_kb_other_tech",
    "admin": "nova_kb_admin",
}

ARTICLE_TITLE = "NOVA KB Test Network Troubleshooting"


def csrf_token(response):
    """Extract a CSRF token from a rendered form."""
    match = re.search(
        rb'name="csrf_token"\s+value="([^"]+)"',
        response.data,
    )

    if not match:
        raise AssertionError(
            f"CSRF token not found. HTTP {response.status_code}"
        )

    return match.group(1).decode()


def create_user(username, role):
    """Create a dedicated test account."""
    user = User(
        full_name=f"NOVA Knowledge {role.title()}",
        username=username,
        email=f"{username}@example.com",
        role=role,
    )

    user.set_password(TEST_PASSWORD)

    db.session.add(user)
    db.session.flush()

    return user


def login_as(client, user):
    """Authenticate through the real login endpoint."""
    with client.session_transaction() as session:
        session.clear()

    login_page = client.get("/auth/login")

    assert login_page.status_code == 200, (
        f"Login page failed for {user.username}: "
        f"HTTP {login_page.status_code}"
    )

    response = client.post(
        "/auth/login",
        data={
            "username_or_email": user.username,
            "password": TEST_PASSWORD,
            "csrf_token": csrf_token(login_page),
        },
        follow_redirects=False,
    )

    assert response.status_code == 302, (
        f"Login failed for {user.username}: "
        f"HTTP {response.status_code}"
    )

    with client.session_transaction() as session:
        authenticated_id = session.get("_user_id")

    assert authenticated_id == str(user.id), (
        f"Incorrect authenticated identity for {user.username}"
    )


def post_with_csrf(client, url, data):
    """
    Submit a POST using a CSRF token from a GET-accessible page.

    For POST-only endpoints, obtain the token from the parent page.
    """
    page = client.get(url)

    if page.status_code == 405:
        page_url = url.rstrip("/").rsplit("/", 1)[0]
        page = client.get(page_url)

    assert page.status_code == 200, (
        f"Could not obtain a CSRF token for {url}. "
        f"HTTP {page.status_code}"
    )

    payload = dict(data)
    payload["csrf_token"] = csrf_token(page)

    return client.post(
        url,
        data=payload,
        follow_redirects=False,
    )


def create_article(
    title,
    author_id,
    category_id,
    published=False,
    summary=None,
    content=None,
):
    """Create an article directly for integration tests."""
    article = KnowledgeArticle(
        title=title,
        slug=generate_slug(title),
        summary=summary or "Temporary Knowledge Base integration test.",
        content=content or (
            "Temporary network troubleshooting instructions "
            "for Knowledge Base integration testing."
        ),
        category_id=category_id,
        author_id=author_id,
        is_published=published,
        view_count=0,
    )

    db.session.add(article)
    db.session.flush()

    return article


def cleanup_test_data(usernames):
    """Remove only the dedicated Knowledge Base test records."""
    users = User.query.filter(
        User.username.in_(usernames)
    ).all()

    user_ids = [user.id for user in users]

    if user_ids:
        articles = KnowledgeArticle.query.filter(
            KnowledgeArticle.author_id.in_(user_ids)
        ).all()

        for article in articles:
            db.session.delete(article)

        db.session.flush()

        for user in users:
            db.session.delete(user)

    db.session.commit()
    print("Knowledge Base test data cleanup: PASS")


def run_tests():
    app = create_app()

    # Disable CSRF validation only for this test application.
    # Production security settings remain unchanged.
    app.config["WTF_CSRF_ENABLED"] = False

    @app.before_request
    def reset_test_login_cache():
        # Prevent Flask-Login's cached identity from leaking between clients.
        g.pop("_login_user", None)

    usernames = list(TEST_USERS.values())

    with app.app_context():
        # Safety check: never run these tests against SmartAttend.
        database_name = db.engine.url.database

        if database_name != "intellidesk":
            raise RuntimeError(
                "Safety check failed: expected database 'intellidesk', "
                f"found {database_name!r}. No test data was created."
            )

        existing = User.query.filter(
            User.username.in_(usernames)
        ).all()

        if existing:
            raise RuntimeError(
                "Dedicated Knowledge Base test accounts already exist: "
                + ", ".join(user.username for user in existing)
                + ". Inspect them before rerunning. "
                "No existing records were deleted."
            )

        category = Category.query.filter_by(
            is_active=True
        ).first()

        if category is None:
            raise RuntimeError(
                "No active category exists. Seed categories first."
            )

        users_created = False

        try:
            user = create_user(
                TEST_USERS["user"],
                "user",
            )

            technician = create_user(
                TEST_USERS["technician"],
                "technician",
            )

            other_technician = create_user(
                TEST_USERS["other_technician"],
                "technician",
            )

            admin = create_user(
                TEST_USERS["admin"],
                "admin",
            )

            db.session.commit()
            users_created = True

            user_client = app.test_client()
            technician_client = app.test_client()
            other_technician_client = app.test_client()
            admin_client = app.test_client()
            anonymous_client = app.test_client()

            login_as(user_client, user)
            login_as(technician_client, technician)
            login_as(other_technician_client, other_technician)
            login_as(admin_client, admin)

            print("\n========== KNOWLEDGE BASE TESTS ==========")

            # 1. Anonymous users must authenticate.
            response = anonymous_client.get(
                "/knowledge/",
                follow_redirects=False,
            )

            assert response.status_code == 302
            assert "/auth/login" in response.headers["Location"]

            print("1. Anonymous access redirects to login: PASS")

            # 2. Authenticated users can open the listing.
            response = user_client.get("/knowledge/")

            assert response.status_code == 200
            assert b"Knowledge Base" in response.data

            print("2. Authenticated article listing: PASS")

            # 3. A technician creates an unpublished article.
            response = post_with_csrf(
                technician_client,
                "/knowledge/new",
                {
                    "title": ARTICLE_TITLE,
                    "summary": (
                        "Troubleshooting common office network problems."
                    ),
                    "content": (
                        "Check the network cable, restart the router, "
                        "and verify the device IP configuration."
                    ),
                    "category_id": str(category.id),
                },
            )

            assert response.status_code == 302, (
                f"Article creation failed: HTTP {response.status_code}\n"
                f"{response.get_data(as_text=True)[:2000]}"
            )

            article = KnowledgeArticle.query.filter_by(
                title=ARTICLE_TITLE
            ).first()

            assert article is not None
            assert article.author_id == technician.id
            assert article.category_id == category.id
            assert article.is_published is False

            article_id = article.id

            print("3. Technician creates an unpublished article: PASS")

            # 4. Article slug is unique.
            assert article.slug

            assert KnowledgeArticle.query.filter_by(
                slug=article.slug
            ).count() == 1

            print("4. Article slug is unique: PASS")

            # 5. Regular users cannot access unpublished articles.
            response = user_client.get(
                f"/knowledge/{article_id}"
            )

            assert response.status_code == 404

            print("5. Unpublished article hidden from users: PASS")

            # 6. The authoring technician can view their draft.
            response = technician_client.get(
                f"/knowledge/{article_id}"
            )

            assert response.status_code == 200
            assert ARTICLE_TITLE.encode() in response.data

            print("6. Technician can view own draft: PASS")

            # 7. Another technician cannot edit the draft.
            response = other_technician_client.get(
                f"/knowledge/{article_id}/edit"
            )

            assert response.status_code == 403

            print(
                "7. Technician cannot edit another technician's article: PASS"
            )

            # 8. Administrators can edit another author's article.
            response = admin_client.get(
                f"/knowledge/{article_id}/edit"
            )

            assert response.status_code == 200

            print(
                "8. Administrator can edit another author's article: PASS"
            )

            # 9. Regular users cannot create articles.
            response = user_client.get(
                "/knowledge/new",
                follow_redirects=False,
            )

            assert response.status_code == 403

            print("9. Regular user cannot create articles: PASS")

            # 10. Administrator publishes the article.
            response = post_with_csrf(
                admin_client,
                f"/knowledge/{article_id}/publication",
                {},
            )

            assert response.status_code == 302

            db.session.expire_all()
            article = db.session.get(
                KnowledgeArticle,
                article_id,
            )

            assert article.is_published is True

            print("10. Administrator publishes article: PASS")

            # 11. Published articles are visible to regular users.
            response = user_client.get("/knowledge/")

            assert response.status_code == 200
            assert ARTICLE_TITLE.encode() in response.data

            response = user_client.get(
                f"/knowledge/{article_id}"
            )

            assert response.status_code == 200

            print("11. Published article is visible to users: PASS")

            # 12. Opening an article increments its view count.
            db.session.expire_all()
            article = db.session.get(
                KnowledgeArticle,
                article_id,
            )

            count_before = article.view_count

            response = user_client.get(
                f"/knowledge/{article_id}"
            )

            assert response.status_code == 200

            db.session.expire_all()
            article = db.session.get(
                KnowledgeArticle,
                article_id,
            )

            assert article.view_count == count_before + 1

            print("12. Article view count increments: PASS")

            # 13. Search by title.
            response = user_client.get(
                "/knowledge/?q=Troubleshooting"
            )

            assert response.status_code == 200
            assert ARTICLE_TITLE.encode() in response.data

            print("13. Article search: PASS")

            # 14. Filter by category.
            response = user_client.get(
                f"/knowledge/?category={category.id}"
            )

            assert response.status_code == 200
            assert ARTICLE_TITLE.encode() in response.data

            print("14. Category filtering: PASS")

            # 15. Technician edits their own published article.
            response = post_with_csrf(
                technician_client,
                f"/knowledge/{article_id}/edit",
                {
                    "title": ARTICLE_TITLE + " Updated",
                    "summary": (
                        "Updated network troubleshooting summary."
                    ),
                    "content": (
                        "Updated instructions: check connectivity, "
                        "verify the network adapter, and test again."
                    ),
                    "category_id": str(category.id),
                },
            )

            assert response.status_code == 302, (
                f"Article edit failed: HTTP {response.status_code}\n"
                f"{response.get_data(as_text=True)[:2000]}"
            )

            db.session.expire_all()
            article = db.session.get(
                KnowledgeArticle,
                article_id,
            )

            assert article.title == ARTICLE_TITLE + " Updated"
            assert article.is_published is True

            print(
                "15. Technician edits own article without unpublishing it: PASS"
            )

            # 16. Technician unpublishes their own article.
            response = post_with_csrf(
                technician_client,
                f"/knowledge/{article_id}/publication",
                {},
            )

            assert response.status_code == 302

            db.session.expire_all()
            article = db.session.get(
                KnowledgeArticle,
                article_id,
            )

            assert article.is_published is False

            response = user_client.get(
                f"/knowledge/{article_id}"
            )

            assert response.status_code == 404

            print("16. Unpublishing hides article from users: PASS")

            # 17. Duplicate titles receive different slugs.
            first = create_article(
                title="NOVA Duplicate Slug Test",
                author_id=technician.id,
                category_id=category.id,
            )

            db.session.flush()

            second = create_article(
                title="NOVA Duplicate Slug Test",
                author_id=technician.id,
                category_id=category.id,
            )

            db.session.flush()

            assert first.slug != second.slug

            print("17. Duplicate titles receive distinct slugs: PASS")

        finally:
            db.session.rollback()

            if users_created:
                cleanup_test_data(usernames)

    print("\nALL KNOWLEDGE BASE TESTS PASSED.")


if __name__ == "__main__":
    run_tests()