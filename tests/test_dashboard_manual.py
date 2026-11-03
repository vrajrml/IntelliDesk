"""Manual integration tests for IntelliDesk dashboards."""

import re
import sys
from pathlib import Path

from flask import g

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app, db
from app.models import User


TEST_PASSWORD = "NovaDashboardPass123!"

TEST_USERS = {
    "user": "nova_dash_user",
    "technician": "nova_dash_technician",
    "admin": "nova_dash_admin",
}


def csrf_token(response):
    """Extract the CSRF token from a rendered form."""
    match = re.search(
        rb'name="csrf_token"\s+value="([^"]+)"',
        response.data,
    )

    if not match:
        raise AssertionError(
            f"CSRF token not found. HTTP {response.status_code}"
        )

    return match.group(1).decode()


def create_test_user(username, role):
    """Create a dedicated dashboard test account."""
    user = User(
        full_name=f"NOVA Dashboard {role.title()}",
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
        f"Login page failed for {user.username}"
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


def check_dashboard(client, expected_heading):
    """Request a dashboard and verify its rendered heading."""
    response = client.get("/dashboard/")

    assert response.status_code == 200, (
        f"Dashboard returned HTTP {response.status_code}"
    )

    page = response.get_data(as_text=True)

    assert expected_heading in page, (
        f"Expected heading {expected_heading!r} not found"
    )

    assert "SLA Monitoring" in page or "SLA Overview" in page, (
        "Expected SLA section was not rendered"
    )

    return response


def cleanup_test_users(usernames):
    """Delete only accounts created by this test."""
    try:
        for user in User.query.filter(
            User.username.in_(usernames)
        ).all():
            db.session.delete(user)

        db.session.commit()
        print("Dashboard test account cleanup: PASS")

    except Exception:
        db.session.rollback()
        print(
            "WARNING: Dashboard test cleanup failed. "
            "Inspect the dedicated nova_dash_* accounts."
        )
        raise


def run_tests():
    app = create_app()

    # Keep this test isolated from production CSRF settings.
    # CSRF remains enabled in the normal application.
    app.config["WTF_CSRF_ENABLED"] = False

    @app.before_request
    def reset_test_login_cache():
        # Separate test clients must not reuse a cached Flask-Login identity.
        g.pop("_login_user", None)

    usernames = list(TEST_USERS.values())
    users_created = False

    with app.app_context():
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
                "Dedicated dashboard test usernames already exist. "
                "Inspect these accounts before rerunning: "
                + ", ".join(user.username for user in existing)
            )

        try:
            users = {
                role: create_test_user(username, role)
                for role, username in TEST_USERS.items()
            }

            db.session.commit()
            users_created = True

            print("Dedicated dashboard test accounts created: PASS")

            # 1. Public dashboard.
            public_client = app.test_client()
            response = public_client.get("/dashboard/")

            assert response.status_code == 200
            assert b"Welcome to IntelliDesk" in response.data
            assert b"Log In" in response.data

            print("Public dashboard: PASS")

            # 2. Regular user dashboard.
            user_client = app.test_client()
            login_as(user_client, users["user"])

            response = check_dashboard(
                user_client,
                "My Dashboard",
            )

            assert b"Create Ticket" in response.data
            print("Regular user dashboard: PASS")

            # 3. Technician dashboard.
            technician_client = app.test_client()
            login_as(technician_client, users["technician"])

            response = check_dashboard(
                technician_client,
                "Technician Dashboard",
            )

            assert b"Assigned Ticket SLA Overview" in response.data
            print("Technician dashboard: PASS")

            # 4. Administrator dashboard.
            admin_client = app.test_client()
            login_as(admin_client, users["admin"])

            response = check_dashboard(
                admin_client,
                "Administrator Dashboard",
            )

            assert b"System-Wide SLA Overview" in response.data
            print("Administrator dashboard: PASS")

        finally:
            # Remove only the dedicated users created by this run.
            db.session.rollback()

            if users_created:
                cleanup_test_users(usernames)

    print("\nAll dashboard tests completed successfully.")


if __name__ == "__main__":
    run_tests()