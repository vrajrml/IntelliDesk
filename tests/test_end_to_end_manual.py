import sys
from pathlib import Path

from flask import g

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app, db
from app.models import (
    Category,
    Ticket,
    TicketComment,
    TicketHistory,
    User,
)


TEST_PASSWORD = "NovaE2ETestPassword123!"

USERNAMES = {
    "user": "nova_e2e_user",
    "technician": "nova_e2e_technician",
    "admin": "nova_e2e_admin",
    "other": "nova_e2e_other",
}

EMAILS = {
    role: f"{username}@example.test"
    for role, username in USERNAMES.items()
}

TICKET_TITLE = "NOVA E2E Network Connectivity Failure"
TICKET_DESCRIPTION = (
    "The office computer cannot connect to the Wi-Fi network. "
    "The network connection repeatedly disconnects and prevents "
    "access to internal applications and online resources."
)

PUBLIC_COMMENT = (
    "Please provide an update on the network connectivity issue."
)

INTERNAL_NOTE = (
    "E2E internal diagnostic note: network adapter and router "
    "connectivity are being investigated."
)


def create_user(role):
    """Create a dedicated integration-test account."""

    user = User(
        username=USERNAMES[role],
        email=EMAILS[role],
        full_name=f"NOVA E2E {role.title()}",
        role=role if role in {"technician", "admin"} else "user",
        is_active=True,
    )

    user.set_password(TEST_PASSWORD)
    db.session.add(user)
    db.session.flush()

    return user


def login(client, username):
    """Authenticate a test client."""

    response = client.post(
        "/auth/login",
        data={
            "username_or_email": username,
            "password": TEST_PASSWORD,
        },
        follow_redirects=False,
    )

    assert response.status_code in (302, 303), (
        f"Login failed for {username}: HTTP {response.status_code}"
    )

    return response


def post(client, url, data, follow_redirects=True):
    """Submit a POST request in the isolated test application."""

    return client.post(
        url,
        data=data,
        follow_redirects=follow_redirects,
    )


def cleanup_test_data():
    """Remove only records belonging to this integration test."""

    test_users = User.query.filter(
        User.username.in_(list(USERNAMES.values()))
    ).all()

    user_ids = [user.id for user in test_users]

    if user_ids:
        test_tickets = Ticket.query.filter(
            db.or_(
                Ticket.requester_id.in_(user_ids),
                Ticket.assignee_id.in_(user_ids),
            )
        ).all()

        ticket_ids = [ticket.id for ticket in test_tickets]

        if ticket_ids:
            TicketComment.query.filter(
                TicketComment.ticket_id.in_(ticket_ids)
            ).delete(synchronize_session=False)

            TicketHistory.query.filter(
                TicketHistory.ticket_id.in_(ticket_ids)
            ).delete(synchronize_session=False)

            db.session.delete_all if False else None

            for ticket in test_tickets:
                db.session.delete(ticket)

        for user in test_users:
            db.session.delete(user)

    db.session.commit()


def run_tests():
    app = create_app()

    # CSRF is disabled only for this isolated manual test application.
    # The real application configuration remains unchanged.
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["TESTING"] = True

    # The manual tests keep an application context open. Clear Flask-Login's
    # request cache before every request so different clients remain isolated.
    @app.before_request
    def clear_login_cache():
        g.pop("_login_user", None)

    with app.app_context():
        database_name = db.session.execute(
            db.text("SELECT DATABASE()")
        ).scalar()

        assert database_name == "intellidesk", (
            f"Safety check failed: connected to {database_name!r}"
        )

        print("Database safety check: PASS")

        existing = User.query.filter(
            User.username.in_(list(USERNAMES.values()))
        ).first()

        assert existing is None, (
            "Dedicated E2E test accounts already exist. "
            "Inspect them before running this test again."
        )

        category = Category.query.filter_by(
            name="Network",
            is_active=True,
        ).first()

        assert category is not None, (
            "Active Network category was not found."
        )

        created_users = []
        seed_ticket_id = None
        ticket_id = None

        try:
            # ------------------------------------------------
            # 1. CREATE DEDICATED TEST ACCOUNTS
            # ------------------------------------------------

            user = create_user("user")
            technician = create_user("technician")
            admin = create_user("admin")
            other_user = create_user("other")

            created_users = [user, technician, admin, other_user]

            db.session.commit()

            print("Dedicated user, technician, and admin accounts: PASS")

            user_id = user.id
            technician_id = technician.id
            admin_id = admin.id
            other_user_id = other_user.id

            # ------------------------------------------------
            # 2. CREATE A MATCHING HISTORICAL TICKET
            # ------------------------------------------------

            seed_ticket = Ticket(
                ticket_number="NOVA-E2E-SEED",
                title=TICKET_TITLE,
                description=TICKET_DESCRIPTION,
                status="open",
                priority="medium",
                requester_id=user_id,
                category_id=category.id,
            )

            db.session.add(seed_ticket)
            db.session.commit()

            seed_ticket_id = seed_ticket.id

            print("Matching historical ticket created: PASS")

            # ------------------------------------------------
            # 3. CREATE ISOLATED CLIENTS AND AUTHENTICATE
            # ------------------------------------------------

            user_client = app.test_client()
            technician_client = app.test_client()
            admin_client = app.test_client()
            other_client = app.test_client()

            login(user_client, USERNAMES["user"])
            login(technician_client, USERNAMES["technician"])
            login(admin_client, USERNAMES["admin"])
            login(other_client, USERNAMES["other"])

            print("All four test accounts authenticated: PASS")

            # ------------------------------------------------
            # 4. CHECK SIMILAR-TICKET RECOMMENDATIONS
            # ------------------------------------------------

            initial_ticket_count = Ticket.query.filter_by(
                requester_id=user_id
            ).count()

            response = post(
                user_client,
                "/tickets/new",
                {
                    "title": TICKET_TITLE,
                    "description": TICKET_DESCRIPTION,
                    "category_id": str(category.id),
                    "action": "find_similar",
                },
            )

            assert response.status_code == 200, (
                "Similar-ticket preview failed: "
                f"HTTP {response.status_code}"
            )

            assert b"NOVA-E2E-SEED" in response.data, (
                "The matching historical ticket was not recommended."
            )

            db.session.expire_all()

            preview_ticket_count = Ticket.query.filter_by(
                requester_id=user_id
            ).count()

            assert preview_ticket_count == initial_ticket_count, (
                "Similar-ticket preview unexpectedly created a ticket."
            )

            print("Similar-ticket recommendation: PASS")
            print("Similar-ticket preview does not create a ticket: PASS")

            # ------------------------------------------------
            # 5. SUBMIT THE ACTUAL TICKET
            # ------------------------------------------------

            response = post(
                user_client,
                "/tickets/new",
                {
                    "title": TICKET_TITLE,
                    "description": TICKET_DESCRIPTION,
                    "category_id": str(category.id),
                    "action": "create_ticket",
                },
                follow_redirects=True,
            )

            assert response.status_code == 200, (
                f"Ticket submission failed: HTTP {response.status_code}"
            )

            ticket = Ticket.query.filter_by(
                requester_id=user_id,
                title=TICKET_TITLE,
            ).order_by(Ticket.id.desc()).first()

            assert ticket is not None, (
                "The submitted ticket was not persisted."
            )

            ticket_id = ticket.id

            assert ticket.ticket_number
            assert ticket.status == "open"
            assert ticket.priority == "medium"
            assert ticket.category_id == category.id
            assert ticket.due_at is not None

            print("Ticket submission and database persistence: PASS")
            print(f"Generated ticket number: {ticket.ticket_number}")

            # ------------------------------------------------
            # 6. VERIFY REAL ML PREDICTIONS
            # ------------------------------------------------

            assert ticket.predicted_category, (
                "Category prediction was not stored. "
                "Check whether the category model is available."
            )

            assert ticket.predicted_priority in {
                "low",
                "medium",
                "high",
                "critical",
            }, (
                "Priority prediction is missing or invalid."
            )

            assert ticket.prediction_confidence is not None
            assert 0 <= ticket.prediction_confidence <= 1

            print(
                "Category ML prediction: PASS "
                f"({ticket.predicted_category}, "
                f"confidence={ticket.prediction_confidence:.4f})"
            )

            print(
                "Priority ML prediction: PASS "
                f"({ticket.predicted_priority})"
            )

            print("User-selected category and default priority preserved: PASS")

            # ------------------------------------------------
            # 7. VERIFY REQUESTER ACCESS CONTROL
            # ------------------------------------------------

            response = other_client.get(
                f"/tickets/{ticket_id}",
                follow_redirects=False,
            )

            assert response.status_code == 403, (
                "Another user was able to access the ticket."
            )

            print("Other-user ticket isolation: PASS")

            # ------------------------------------------------
            # 8. ADMIN ASSIGNS THE TECHNICIAN
            # ------------------------------------------------

            response = post(
                admin_client,
                f"/tickets/{ticket_id}/assign",
                {"assignee_id": str(technician_id)},
            )

            assert response.status_code == 200

            db.session.expire_all()
            ticket = db.session.get(Ticket, ticket_id)

            assert ticket.assignee_id == technician_id

            print("Administrator technician assignment: PASS")

            # ------------------------------------------------
            # 9. TECHNICIAN INVESTIGATES THE TICKET
            # ------------------------------------------------

            response = post(
                technician_client,
                f"/tickets/{ticket_id}/update",
                {
                    "status": "in_progress",
                    "priority": "high",
                },
            )

            assert response.status_code == 200

            db.session.expire_all()
            ticket = db.session.get(Ticket, ticket_id)

            assert ticket.status == "in_progress"
            assert ticket.priority == "high"

            print("Technician status and priority update: PASS")

            # ------------------------------------------------
            # 10. TECHNICIAN ADDS AN INTERNAL NOTE
            # ------------------------------------------------

            response = post(
                technician_client,
                f"/tickets/{ticket_id}/comment",
                {
                    "message": INTERNAL_NOTE,
                    "is_internal": "1",
                },
            )

            assert response.status_code == 200

            internal_comment = TicketComment.query.filter_by(
                ticket_id=ticket_id,
                user_id=technician_id,
                message=INTERNAL_NOTE,
            ).first()

            assert internal_comment is not None
            assert internal_comment.is_internal is True

            print("Technician internal note: PASS")

            # ------------------------------------------------
            # 11. USER ADDS A PUBLIC COMMENT
            # ------------------------------------------------

            response = post(
                user_client,
                f"/tickets/{ticket_id}/comment",
                {"message": PUBLIC_COMMENT},
            )

            assert response.status_code == 200

            public_comment = TicketComment.query.filter_by(
                ticket_id=ticket_id,
                user_id=user_id,
                message=PUBLIC_COMMENT,
            ).first()

            assert public_comment is not None
            assert public_comment.is_internal is False

            print("Requester public comment: PASS")

            # ------------------------------------------------
            # 12. VERIFY COMMENT VISIBILITY
            # ------------------------------------------------

            response = user_client.get(
                f"/tickets/{ticket_id}"
            )

            assert response.status_code == 200
            assert PUBLIC_COMMENT.encode() in response.data
            assert INTERNAL_NOTE.encode() not in response.data

            print("Public comment visible to requester: PASS")
            print("Internal note hidden from requester: PASS")

            # ------------------------------------------------
            # 13. TECHNICIAN RESOLVES THE TICKET
            # ------------------------------------------------

            response = post(
                technician_client,
                f"/tickets/{ticket_id}/update",
                {
                    "status": "resolved",
                    "priority": "high",
                },
            )

            assert response.status_code == 200

            db.session.expire_all()
            ticket = db.session.get(Ticket, ticket_id)

            assert ticket.status == "resolved"
            assert ticket.resolved_at is not None

            print("Technician ticket resolution: PASS")
            print("Resolution timestamp recorded: PASS")

            # ------------------------------------------------
            # 14. VERIFY REQUESTER CAN REVIEW RESOLUTION
            # ------------------------------------------------

            response = user_client.get(
                f"/tickets/{ticket_id}"
            )

            assert response.status_code == 200
            assert b"resolved" in response.data.lower()
            assert PUBLIC_COMMENT.encode() in response.data
            assert INTERNAL_NOTE.encode() not in response.data

            print("Requester can review resolved ticket: PASS")

            # ------------------------------------------------
            # 15. VERIFY COMPLETE AUDIT HISTORY
            # ------------------------------------------------

            history_entries = TicketHistory.query.filter_by(
                ticket_id=ticket_id
            ).all()

            history_fields = {
                entry.field_name
                for entry in history_entries
            }

            expected_fields = {
                "created",
                "assignee",
                "status",
                "priority",
                "comment",
            }

            missing_fields = expected_fields - history_fields

            assert not missing_fields, (
                "Missing audit history fields: "
                + ", ".join(sorted(missing_fields))
            )

            assert len(history_entries) >= 6, (
                "Expected more lifecycle audit-history entries."
            )

            print("Complete ticket lifecycle audit history: PASS")

            # ------------------------------------------------
            # 16. VERIFY FINAL ADMIN VIEW
            # ------------------------------------------------

            response = admin_client.get(
                f"/tickets/{ticket_id}"
            )

            assert response.status_code == 200
            assert b"Recent History" in response.data
            assert b"Assign Technician" in response.data

            print("Administrator final ticket view: PASS")

            print("\nTicket lifecycle summary:")
            print(f"  Ticket: {ticket.ticket_number}")
            print(f"  Requester: {USERNAMES['user']}")
            print(f"  Technician: {USERNAMES['technician']}")
            print(f"  Predicted category: {ticket.predicted_category}")
            print(f"  Predicted priority: {ticket.predicted_priority}")
            print(f"  Final priority: {ticket.priority}")
            print(f"  Final status: {ticket.status}")
            print(f"  Audit entries: {len(history_entries)}")

        finally:
            db.session.rollback()

            # Delete only tickets and users created by this test.
            test_user_ids = [
                user.id for user in created_users
            ]

            if test_user_ids:
                test_tickets = Ticket.query.filter(
                    db.or_(
                        Ticket.requester_id.in_(test_user_ids),
                        Ticket.assignee_id.in_(test_user_ids),
                    )
                ).all()

                test_ticket_ids = [
                    ticket.id for ticket in test_tickets
                ]

                if test_ticket_ids:
                    TicketComment.query.filter(
                        TicketComment.ticket_id.in_(test_ticket_ids)
                    ).delete(synchronize_session=False)

                    TicketHistory.query.filter(
                        TicketHistory.ticket_id.in_(test_ticket_ids)
                    ).delete(synchronize_session=False)

                    for test_ticket in test_tickets:
                        db.session.delete(test_ticket)

                for test_user in created_users:
                    db.session.delete(test_user)

                db.session.commit()

            print("\nE2E test data cleanup: PASS")


if __name__ == "__main__":
    run_tests()
