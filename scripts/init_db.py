import sys
from pathlib import Path

# Add the IntelliDesk project root to Python's import path.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app, db
from app.models import (
    User,
    Category,
    Ticket,
    TicketComment,
    TicketFeedback,
    TicketHistory,
    KnowledgeArticle,
)


def initialize_database():
    """Create missing tables in the IntelliDesk database."""

    app = create_app()

    with app.app_context():
        # Safety check: never initialize a different database.
        database_name = db.engine.url.database

        if database_name != "intellidesk":
            raise RuntimeError(
                "Database initialization stopped. "
                f"Expected 'intellidesk', got '{database_name}'. "
                "Check the DATABASE_URL in your .env file."
            )

        print(f"Connected database: {database_name}")
        print("Creating missing tables...")

        # Create missing tables without dropping existing ones.
        db.create_all()

        # Verify that all expected tables exist.
        inspector = db.inspect(db.engine)
        existing_tables = sorted(inspector.get_table_names())

        expected_tables = {
            "users",
            "categories",
            "tickets",
            "ticket_comments",
            "ticket_feedback",
            "ticket_history",
            "knowledge_articles",
        }

        print("\nTables found:")

        for table in existing_tables:
            print(f"  - {table}")

        missing_tables = expected_tables - set(existing_tables)

        if missing_tables:
            raise RuntimeError(
                f"Missing tables: {sorted(missing_tables)}"
            )

        print("\nAll seven IntelliDesk tables are present.")
        print("Database initialization completed successfully!")


if __name__ == "__main__":
    initialize_database()