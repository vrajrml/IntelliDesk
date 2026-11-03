"""
Create a dedicated technician account for Project NOVA - IntelliDesk.

Security features:
- Password is entered privately using getpass.
- Passwords are hashed by the User model.
- Duplicate usernames and email addresses are rejected.
- Existing accounts are never modified.
"""

import getpass
import sys

from sqlalchemy import or_

from app import create_app, db
from app.models import User


def prompt_required(label, max_length=None):
    """Prompt for a required value and validate its length."""
    while True:
        value = input(f"{label}: ").strip()

        if not value:
            print("This field cannot be empty.")
            continue

        if max_length and len(value) > max_length:
            print(
                f"This field cannot exceed {max_length} characters."
            )
            continue

        return value


def prompt_email():
    """Collect and validate a basic email address."""
    while True:
        email = prompt_required("Technician email", max_length=120)

        if (
            "@" not in email
            or email.startswith("@")
            or email.endswith("@")
            or "." not in email.rsplit("@", 1)[-1]
        ):
            print("Please enter a valid email address.")
            continue

        return email.lower()


def prompt_password():
    """Collect a password privately and require confirmation."""
    while True:
        password = getpass.getpass(
            "Technician password (minimum 12 characters): "
        )

        if len(password) < 12:
            print("Password must contain at least 12 characters.")
            continue

        confirmation = getpass.getpass(
            "Confirm technician password: "
        )

        if password != confirmation:
            print("Passwords do not match. Try again.")
            continue

        return password


def main():
    """Create a technician account without modifying existing users."""
    app = create_app()

    with app.app_context():
        print("\nProject NOVA | IntelliDesk")
        print("Create Technician Account")
        print("-" * 36)

        username = prompt_required(
            "Technician username",
            max_length=80,
        )

        full_name = prompt_required(
            "Technician full name",
            max_length=120,
        )

        email = prompt_email()

        existing_user = User.query.filter(
            or_(
                User.username == username,
                User.email == email,
            )
        ).first()

        if existing_user:
            print(
                "\nCannot create technician: "
                "the username or email is already registered."
            )
            sys.exit(1)

        password = prompt_password()

        technician = User(
            username=username,
            email=email,
            full_name=full_name,
            role="technician",
            is_active=True,
        )

        technician.set_password(password)

        try:
            db.session.add(technician)
            db.session.commit()

        except Exception:
            db.session.rollback()
            app.logger.exception(
                "Technician account creation failed."
            )
            print(
                "\nTechnician account creation failed. "
                "Check the application logs."
            )
            sys.exit(1)

        print("\nTechnician account created successfully.")
        print(f"Username: {technician.username}")
        print(f"Full name: {technician.full_name}")
        print(f"Email: {technician.email}")
        print(f"Role: {technician.role}")
        print(f"Account ID: {technician.id}")
        print("\nKeep the password private.")


if __name__ == "__main__":
    main()