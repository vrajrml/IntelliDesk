import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app, db
from app.models import Category


DEFAULT_CATEGORIES = [
    {
        "name": "Hardware",
        "description": "Computers, printers, peripherals, and physical equipment.",
    },
    {
        "name": "Software",
        "description": "Software installation, application errors, and updates.",
    },
    {
        "name": "Network",
        "description": "Wi-Fi, internet connectivity, and network access.",
    },
    {
        "name": "Account Access",
        "description": "Login problems, password resets, and access permissions.",
    },
    {
        "name": "Email & Communication",
        "description": "Email, messaging, and communication tools.",
    },
    {
        "name": "Other",
        "description": "Requests that do not fit another category.",
    },
]


def seed_categories():
    """Insert default categories without duplicating existing records."""

    app = create_app()

    with app.app_context():
        database_name = db.engine.url.database

        if database_name != "intellidesk":
            raise RuntimeError(
                "Seeding stopped for safety. "
                f"Expected 'intellidesk', got '{database_name}'."
            )

        added_count = 0

        for item in DEFAULT_CATEGORIES:
            existing = db.session.query(Category).filter_by(
                name=item["name"]
            ).first()

            if existing is None:
                db.session.add(Category(**item))
                added_count += 1

        db.session.commit()

        print(f"Database: {database_name}")
        print(f"New categories added: {added_count}")
        print("\nAvailable categories:")

        categories = db.session.query(Category).order_by(Category.name).all()

        for category in categories:
            print(f"  {category.id}. {category.name}")


if __name__ == "__main__":
    try:
        seed_categories()
    except Exception:
        db.session.rollback()
        raise