import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app, db
from app.models import Category, Ticket, TicketHistory, User


def extract_csrf_token(response):
    match = re.search(
        rb'name="csrf_token"\s+value="([^"]+)"',
        response.data,
    )
    if not match:
        raise AssertionError("CSRF token was not found in the HTML form.")
    return match.group(1).decode("utf-8")


def test_ticket_creation():
    app = create_app()

    with app.app_context():
        if db.engine.url.database != "intellidesk":
            raise RuntimeError(
                "Safety check failed: refusing to test another database."
            )

        username = "nova_ticket_test"
        email = "nova_ticket_test@example.com"

        # Refuse to delete or reuse an existing account.
        existing = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()

        if existing:
            raise RuntimeError(
                "The dedicated test account already exists. "
                "Inspect it before running this test again."
            )

        category = Category.query.filter_by(is_active=True).first()
        if category is None:
            raise RuntimeError("No active ticket category is available.")

        user = User(
            full_name="NOVA Ticket Test",
            username=username,
            email=email,
            role="user",
        )
        user.set_password("NovaTicketPass123!")

        db.session.add(user)
        db.session.commit()

        ticket_id = None

        try:
            client = app.test_client()

            # Log in using the real login route.
            response = client.get("/auth/login")
            assert response.status_code == 200

            token = extract_csrf_token(response)

            response = client.post(
                "/auth/login",
                data={
                    "csrf_token": token,
                    "username_or_email": username,
                    "password": "NovaTicketPass123!",
                },
                follow_redirects=True,
            )

            assert response.status_code == 200
            print("Test user login: PASS")

            # Open the ticket form and obtain its CSRF token.
            response = client.get("/tickets/new")
            assert response.status_code == 200
            assert b"Create a Service Ticket" in response.data

            token = extract_csrf_token(response)
            print("Ticket creation form: PASS")

            # Submit a ticket through the actual application route.
            response = client.post(
                "/tickets/new",
                data={
                    "csrf_token": token,
                    "title": "NOVA ticket creation test",
                    "description": (
                        "This is a temporary test ticket used to verify "
                        "ticket creation and database persistence."
                    ),
                    "category_id": str(category.id),
                },
                follow_redirects=True,
            )

            if response.status_code != 200:
                print("Ticket submission HTTP status:", response.status_code)
                print(
                    response.data.decode(
                        "utf-8", errors="replace"
                    )[:3000]
                )

            assert response.status_code == 200
            assert b"was created successfully" in response.data

            ticket = Ticket.query.filter_by(
                requester_id=user.id,
                title="NOVA ticket creation test",
            ).first()

            assert ticket is not None, "Ticket was not saved to MySQL."
            ticket_id = ticket.id

            assert ticket.status == "open"
            assert ticket.priority == "medium"
            assert ticket.category_id == category.id

            print("Ticket submission: PASS")
            print("Ticket database persistence: PASS")
            print("Default status and priority: PASS")

            # Verify ticket history.
            history = TicketHistory.query.filter_by(
                ticket_id=ticket.id,
                field_name="created",
            ).first()

            assert history is not None, (
                "Ticket was created, but its history entry is missing."
            )
            print("Ticket creation history: PASS")

            # Verify the detail page.
            response = client.get(f"/tickets/{ticket.id}")
            assert response.status_code == 200
            assert b"NOVA ticket creation test" in response.data
            print("Ticket detail page: PASS")

            # Verify the listing page.
            response = client.get("/tickets/")
            assert response.status_code == 200
            assert b"NOVA ticket creation test" in response.data
            print("Ticket listing page: PASS")

        finally:
            # Delete only the ticket created by this test.
            if ticket_id is not None:
                TicketHistory.query.filter_by(
                    ticket_id=ticket_id
                ).delete(synchronize_session=False)

                ticket = db.session.get(Ticket, ticket_id)
                if ticket is not None:
                    db.session.delete(ticket)
                    db.session.commit()

            # Delete only this test's dedicated user.
            test_user = User.query.filter_by(username=username).first()
            if test_user is not None:
                db.session.delete(test_user)
                db.session.commit()

            print("Test data cleanup: PASS")


if __name__ == "__main__":
    test_ticket_creation()
    print("\nAll ticket creation tests completed successfully.")
