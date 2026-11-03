"""Create an administrator account securely for IntelliDesk."""

import getpass
import sys

from app import create_app, db
from app.models import User


def main():
    app = create_app()

    with app.app_context():
        username = input("Admin username: ").strip()
        email = input("Admin email: ").strip()
        full_name = input("Admin full name: ").strip()

        if not username or not email or not full_name:
            print("Username, email, and full name are required.")
            sys.exit(1)

        existing_username = User.query.filter_by(
            username=username
        ).first()

        if existing_username:
            print("That username already exists.")
            sys.exit(1)

        existing_email = User.query.filter_by(
            email=email
        ).first()

        if existing_email:
            print("That email address already exists.")
            sys.exit(1)

        password = getpass.getpass("Admin password (minimum 12 characters): ")
        confirmation = getpass.getpass("Confirm admin password: ")

        if len(password) < 12:
            print("Password must contain at least 12 characters.")
            sys.exit(1)

        if password != confirmation:
            print("Passwords do not match.")
            sys.exit(1)

        admin = User(
            username=username,
            email=email,
            full_name=full_name,
            role="admin",
            is_active=True,
        )
        admin.set_password(password)

        try:
            db.session.add(admin)
            db.session.commit()
        except Exception:
            db.session.rollback()
            print("Admin account creation failed.")
            raise

        print("\nAdministrator account created successfully.")
        print(f"Username: {admin.username}")
        print(f"Role: {admin.role}")
        print("Your password was not displayed or stored in this script.")


if __name__ == "__main__":
    main()
