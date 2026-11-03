import re
import sys
from pathlib import Path

# Add the IntelliDesk project root to Python's import path.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app, db
from app.models import User


def extract_csrf_token(response):
    """Extract the CSRF token from an HTML form."""

    match = re.search(
        rb'name="csrf_token"\s+value="([^"]+)"',
        response.data,
    )

    if not match:
        raise AssertionError(
            "CSRF token was not found in the rendered HTML response."
        )

    return match.group(1).decode("utf-8")


def test_inactive_account_security():

    app = create_app()

    with app.app_context():

        # Safety check: never run against another database.
        if db.engine.url.database != "intellidesk":
            raise RuntimeError(
                "Safety check failed: refusing to test another database."
            )

        username = "nova_security_inactive"
        email = "nova_security_inactive@example.com"
        password = "NovaSecurityPass123!"

        # Remove only the dedicated test account if it already exists.
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()

        if existing_user:
            db.session.delete(existing_user)
            db.session.commit()

        try:

            # ------------------------------------------------
            # CREATE INACTIVE TEST ACCOUNT
            # ------------------------------------------------

            user = User(
                username=username,
                email=email,
                full_name="NOVA Security Test",
                role="user",
                is_active=False,
            )

            user.set_password(password)

            db.session.add(user)
            db.session.commit()

            user_id = user.id

            print("Inactive test account creation: PASS")

            # ------------------------------------------------
            # TEST 1: INACTIVE ACCOUNT CANNOT LOG IN
            # ------------------------------------------------

            client = app.test_client()

            response = client.get("/auth/login")

            assert response.status_code == 200, (
                "Login page did not load."
            )

            csrf_token = extract_csrf_token(response)

            response = client.post(
                "/auth/login",
                data={
                    "csrf_token": csrf_token,
                    "username_or_email": username,
                    "password": password,
                },
                follow_redirects=False,
            )

            assert response.status_code == 403, (
                f"Expected HTTP 403 for inactive account, "
                f"received HTTP {response.status_code}."
            )

            assert b"This account is inactive" in response.data, (
                "Inactive-account message was not displayed."
            )

            print("Inactive account login rejection: PASS")

            # ------------------------------------------------
            # TEST 2: INACTIVE ACCOUNT CANNOT ACCESS DASHBOARD
            # ------------------------------------------------

            response = client.get("/dashboard/")

            assert response.status_code == 200, (
                "Public dashboard did not load."
            )

            assert b"Create Account" in response.data, (
                "Inactive account was treated as authenticated."
            )

            print("Inactive account dashboard protection: PASS")

            # ------------------------------------------------
            # TEST 3: EXISTING SESSION CANNOT LOAD INACTIVE USER
            # ------------------------------------------------

            # Simulate a previously authenticated session.
            with client.session_transaction() as session:
                session["_user_id"] = str(user_id)
                session["_fresh"] = True

            response = client.get("/dashboard/")

            assert response.status_code == 200, (
                "Dashboard did not load after inactive-session check."
            )

            assert b"Create Account" in response.data, (
                "Inactive account retained authenticated access."
            )

            print("Inactive account existing-session rejection: PASS")

            # ------------------------------------------------
            # TEST 4: ACCOUNT REMAINS INACTIVE IN DATABASE
            # ------------------------------------------------

            db.session.expire_all()

            stored_user = db.session.get(User, user_id)

            assert stored_user is not None, (
                "Security test account unexpectedly disappeared."
            )

            assert stored_user.is_active is False, (
                "Inactive account status unexpectedly changed."
            )

            print("Inactive account database state: PASS")

        finally:

            # ------------------------------------------------
            # CLEANUP: REMOVE ONLY OUR TEST ACCOUNT
            # ------------------------------------------------

            test_user = User.query.filter_by(
                username=username
            ).first()

            if test_user:
                db.session.delete(test_user)
                db.session.commit()

                print("Security test account cleanup: PASS")


if __name__ == "__main__":

    test_inactive_account_security()

    print("\nAll inactive-account security tests completed successfully.")