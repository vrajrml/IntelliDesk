import re
import sys
from pathlib import Path

# Add the IntelliDesk project root to Python's import path.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app, db
from app.models import User


def extract_csrf_token(response):
    """Extract the signed CSRF token rendered in an HTML form."""
    match = re.search(
        rb'name="csrf_token"\s+value="([^"]+)"',
        response.data,
    )

    if not match:
        raise AssertionError(
            "CSRF token was not found in the rendered HTML response."
        )

    return match.group(1).decode("utf-8")


def test_registration_and_password_hashing():
    app = create_app()

    with app.app_context():

        # Safety check: never run this test against another database.
        if db.engine.url.database != "intellidesk":
            raise RuntimeError(
                "Safety check failed: refusing to test another database."
            )

        client = app.test_client()

        username = "testuser_nova"
        email = "testuser_nova@example.com"
        password = "NovaTestPass123!"

        # Remove only the dedicated test account if it already exists.
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()

        if existing_user:
            db.session.delete(existing_user)
            db.session.commit()

        try:
            # -----------------------------------------------
            # TEST 1: Registration page and CSRF protection
            # -----------------------------------------------
            response = client.get("/auth/register")
            assert response.status_code == 200, (
                "Registration page did not return HTTP 200."
            )

            csrf_token = extract_csrf_token(response)

            # -----------------------------------------------
            # TEST 2: Register a new user
            # -----------------------------------------------
            response = client.post(
                "/auth/register",
                data={
                    "csrf_token": csrf_token,
                    "full_name": "NOVA Test User",
                    "username": username,
                    "email": email,
                    "password": password,
                    "confirm_password": password,
                },
                follow_redirects=True,
            )

            if response.status_code != 200:
                print("Registration status:", response.status_code)
                print(
                    response.data.decode(
                        "utf-8", errors="replace"
                    )[:3000]
                )

            assert response.status_code == 200, (
                "Registration did not complete successfully."
            )

            assert b"Your account has been created" in response.data, (
                "Registration success message was not found."
            )

            print("Registration: PASS")

            # -----------------------------------------------
            # TEST 3: Verify the stored account
            # -----------------------------------------------
            user = User.query.filter_by(username=username).first()

            assert user is not None, "Registered user was not found."
            assert user.email == email
            assert user.role == "user", (
                "Public registration did not assign the user role."
            )

            print("Account creation: PASS")
            print("Default role assignment: PASS")

            # -----------------------------------------------
            # TEST 4: Password hashing and verification
            # -----------------------------------------------
            assert user.password_hash != password, (
                "Password appears to be stored in plain text."
            )

            assert user.check_password(password), (
                "Password verification failed."
            )

            assert not user.check_password("WrongPassword123!"), (
                "Incorrect password was accepted."
            )

            print("Password hashing: PASS")
            print("Correct password verification: PASS")
            print("Incorrect password rejection: PASS")

            # -----------------------------------------------
            # TEST 5: Login page and CSRF token
            # -----------------------------------------------
            response = client.get("/auth/login")
            assert response.status_code == 200, (
                "Login page did not return HTTP 200."
            )

            csrf_token = extract_csrf_token(response)

            # -----------------------------------------------
            # TEST 6: Login using the registered credentials
            # -----------------------------------------------
            response = client.post(
                "/auth/login",
                data={
                    "csrf_token": csrf_token,
                    "username_or_email": username,
                    "password": password,
                },
                follow_redirects=True,
            )

            if response.status_code != 200:
                print("Login status:", response.status_code)
                print(
                    response.data.decode(
                        "utf-8", errors="replace"
                    )[:3000]
                )

            assert response.status_code == 200, (
                "Login did not complete successfully."
            )

            assert b"My Dashboard" in response.data, (
                "Authenticated dashboard was not displayed."
            )

            print("Login: PASS")
            print("Authenticated dashboard: PASS")

            # -----------------------------------------------
            # TEST 7: Logout with a valid CSRF token
            # -----------------------------------------------
            # The authenticated dashboard extends base.html,
            # which contains the POST logout form and its token.
            csrf_token = extract_csrf_token(response)

            response = client.post(
                "/auth/logout",
                data={"csrf_token": csrf_token},
                follow_redirects=True,
            )

            assert response.status_code == 200, (
                "Logout did not complete successfully."
            )

            assert b"You have been logged out" in response.data, (
                "Logout confirmation message was not found."
            )

            print("Logout: PASS")

            # Confirm the session is no longer authenticated.
            response = client.get("/dashboard/")

            assert b"Create Account" in response.data, (
                "User may still be authenticated after logout."
            )

            print("Session termination: PASS")

        finally:
            # Remove only the dedicated test account.
            # Never delete unrelated users or project data.
            test_user = User.query.filter_by(
                username=username
            ).first()

            if test_user:
                db.session.delete(test_user)
                db.session.commit()

                print("Test account cleanup: PASS")


if __name__ == "__main__":
    test_registration_and_password_hashing()
    print("\nAll authentication tests completed successfully.")
