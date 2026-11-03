import re
import sys
from pathlib import Path
from flask import g

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app, db
from app.models import Category, Ticket, TicketComment, TicketHistory, User


TEST_PASSWORD = "NovaWorkflowPass123!"

TEST_USERS = {
    "requester": "nova_wf_requester",
    "technician": "nova_wf_technician",
    "admin": "nova_wf_admin",
    "other": "nova_wf_other",
}

TEST_TICKET_TITLE = "NOVA workflow integration test"


def csrf_token(response):
    match = re.search(
        rb'name="csrf_token"\s+value="([^"]+)"',
        response.data,
    )

    if not match:
        raise AssertionError(
            f"CSRF token not found. HTTP {response.status_code}"
        )

    return match.group(1).decode()


def login_as(client, user):
    """Authenticate a dedicated test client through the real login route."""

    # Ensure this test client starts with a clean session.
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
        f"HTTP {response.status_code}\n"
        f"Response body:\n{response.get_data(as_text=True)[:3000]}"
    )

    dashboard = client.get("/dashboard/")

    assert dashboard.status_code == 200, (
        f"Dashboard failed for {user.username}: "
        f"HTTP {dashboard.status_code}"
    )

    with client.session_transaction() as session:
        authenticated_id = session.get("_user_id")

    assert authenticated_id == str(user.get_id()), (
        f"Wrong authenticated identity for {user.username}: "
        f"expected {user.get_id()}, got {authenticated_id}"
    )

    print(f"Authentication verified: {user.username} (ID {user.id})")
    return dashboard


def post_with_csrf(client, url, data, follow_redirects=True):
    """
    Obtain CSRF from a GET-accessible page and POST to the
    requested endpoint.

    Update, assign, and comment endpoints may accept POST only.
    In that case, obtain the token from the parent ticket detail page.
    """
    page_url = url
    page = client.get(page_url)

    if page.status_code == 405:
        # Example: /tickets/4/update -> /tickets/4
        page_url = url.rstrip("/").rsplit("/", 1)[0]
        page = client.get(page_url)

    assert page.status_code == 200, (
        f"Could not open a CSRF token page for {url}. "
        f"Tried {page_url}; HTTP {page.status_code}"
    )

    payload = dict(data)
    payload["csrf_token"] = csrf_token(page)

    return client.post(
        url,
        data=payload,
        follow_redirects=follow_redirects,
    )


def create_user(username, role):
    user = User(
        full_name=f"NOVA Test {role.title()}",
        username=username,
        email=f"{username}@example.com",
        role=role,
    )
    user.set_password(TEST_PASSWORD)
    db.session.add(user)
    db.session.flush()
    return user


def cleanup_test_data(ticket_id, usernames):
    """Remove only the dedicated workflow test records."""
    if ticket_id is not None:
        TicketComment.query.filter_by(
            ticket_id=ticket_id
        ).delete(synchronize_session=False)

        TicketHistory.query.filter_by(
            ticket_id=ticket_id
        ).delete(synchronize_session=False)

        test_ticket = db.session.get(Ticket, ticket_id)

        if test_ticket is not None:
            db.session.delete(test_ticket)

    db.session.flush()

    for user in User.query.filter(
        User.username.in_(usernames)
    ).all():
        db.session.delete(user)

    db.session.commit()
    print("Test data cleanup: PASS")


def run_tests():
    app = create_app()

    # This workflow test focuses on ticket permissions and behavior.
    # Disable CSRF validation only for this test application.
    # Production application security settings remain unchanged.
    app.config["WTF_CSRF_ENABLED"] = False

    @app.before_request
    def reset_test_login_cache():
        # The workflow test keeps an application context open for database
        # assertions. Prevent Flask-Login's cached identity from leaking
        # between requests made by different test clients.
        g.pop("_login_user", None)

    with app.app_context():
        # Never run this test against another database.
        database_name = db.engine.url.database

        if database_name != "intellidesk":
            raise RuntimeError(
                "Safety check failed: expected database 'intellidesk', "
                f"found {database_name!r}. No tests were run."
            )

        usernames = list(TEST_USERS.values())

        existing = User.query.filter(
            User.username.in_(usernames)
        ).all()

        if existing:
            names = ", ".join(user.username for user in existing)
            raise RuntimeError(
                f"Workflow test accounts already exist: {names}. "
                "Inspect them before rerunning. No records were deleted."
            )

        category = Category.query.filter_by(is_active=True).first()

        if category is None:
            raise RuntimeError(
                "No active category exists. Seed categories first."
            )

        ticket_id = None
        users_created = False

        try:
            requester = create_user(
                TEST_USERS["requester"], "user"
            )
            technician = create_user(
                TEST_USERS["technician"], "technician"
            )
            admin = create_user(
                TEST_USERS["admin"], "admin"
            )
            other_user = create_user(
                TEST_USERS["other"], "user"
            )

            db.session.commit()
            users_created = True

            requester_client = app.test_client()
            technician_client = app.test_client()
            admin_client = app.test_client()
            other_client = app.test_client()

            login_as(requester_client, requester)
            login_as(technician_client, technician)
            login_as(admin_client, admin)
            login_as(other_client, other_user)

            # 1. Ticket creation.
            response = requester_client.get("/tickets/new")
            assert response.status_code == 200

            response = post_with_csrf(
                requester_client,
                "/tickets/new",
                {
                    "title": TEST_TICKET_TITLE,
                    "description": (
                        "Temporary integration test for ticket status, "
                        "assignment, comments, and access control."
                    ),
                    "category_id": str(category.id),
                },
            )

            assert response.status_code == 200, (
                f"Ticket creation failed: HTTP {response.status_code}"
            )

            ticket = Ticket.query.filter_by(
                requester_id=requester.id,
                title=TEST_TICKET_TITLE,
            ).first()

            assert ticket is not None, "Ticket was not saved."
            ticket_id = ticket.id

            assert ticket.status == "open"
            assert ticket.priority == "medium"

            print("Ticket creation and defaults: PASS")

            # 2. Requesters cannot update ticket status.
            response = post_with_csrf(
                requester_client,
                f"/tickets/{ticket_id}/update",
                {"status": "in_progress", "priority": "high"},
                follow_redirects=False,
            )

            assert response.status_code == 403
            print("Requester cannot update ticket status: PASS")

            # 3. Requesters cannot view another user's ticket.
            response = other_client.get(f"/tickets/{ticket_id}")

            assert response.status_code == 403
            print("Requester ticket isolation: PASS")

            # 4. Technicians can update status and priority.
            response = post_with_csrf(
                technician_client,
                f"/tickets/{ticket_id}/update",
                {"status": "in_progress", "priority": "high"},
            )

            assert response.status_code == 200

            db.session.expire_all()
            ticket = db.session.get(Ticket, ticket_id)

            assert ticket.status == "in_progress"
            assert ticket.priority == "high"

            print("Technician status and priority update: PASS")

            # 5. Resolving a ticket records a timestamp.
            response = post_with_csrf(
                technician_client,
                f"/tickets/{ticket_id}/update",
                {"status": "resolved", "priority": "high"},
            )

            assert response.status_code == 200

            db.session.expire_all()
            ticket = db.session.get(Ticket, ticket_id)

            assert ticket.status == "resolved"
            assert ticket.resolved_at is not None

            print("Resolution timestamp: PASS")

            # 6. Reopening clears the resolution timestamp.
            response = post_with_csrf(
                technician_client,
                f"/tickets/{ticket_id}/update",
                {"status": "in_progress", "priority": "high"},
            )

            assert response.status_code == 200

            db.session.expire_all()
            ticket = db.session.get(Ticket, ticket_id)

            assert ticket.status == "in_progress"
            assert ticket.resolved_at is None

            print("Reopening clears resolution timestamp: PASS")

            # 7. Administrators can assign active technicians.
            response = post_with_csrf(
                admin_client,
                f"/tickets/{ticket_id}/assign",
                {"assignee_id": str(technician.id)},
            )

            assert response.status_code == 200

            db.session.expire_all()
            ticket = db.session.get(Ticket, ticket_id)

            assert ticket.assignee_id == technician.id

            print("Administrator technician assignment: PASS")

            # 8. Technicians cannot use administrator-only assignment.
            response = post_with_csrf(
                technician_client,
                f"/tickets/{ticket_id}/assign",
                {"assignee_id": str(technician.id)},
                follow_redirects=False,
            )

            assert response.status_code == 403

            print("Administrator-only assignment permission: PASS")

            # 9. Requesters can add public comments.
            public_message = (
                "Please let me know when there is an update."
            )

            response = post_with_csrf(
                requester_client,
                f"/tickets/{ticket_id}/comment",
                {"message": public_message},
            )

            assert response.status_code == 200

            public_comment = TicketComment.query.filter_by(
                ticket_id=ticket_id,
                user_id=requester.id,
                message=public_message,
            ).first()

            assert public_comment is not None
            assert public_comment.is_internal is False

            print("Requester public comment: PASS")

            # 10. Technicians can add internal notes.
            internal_message = "Internal diagnostic note for testing."

            response = post_with_csrf(
                technician_client,
                f"/tickets/{ticket_id}/comment",
                {
                    "message": internal_message,
                    "is_internal": "1",
                },
            )

            assert response.status_code == 200

            internal_comment = TicketComment.query.filter_by(
                ticket_id=ticket_id,
                user_id=technician.id,
                message=internal_message,
            ).first()

            assert internal_comment is not None
            assert internal_comment.is_internal is True

            print("Technician internal note: PASS")

            # 11. Requesters cannot see internal notes.
            response = requester_client.get(
                f"/tickets/{ticket_id}"
            )

            assert response.status_code == 200
            assert internal_message.encode() not in response.data
            assert public_message.encode() in response.data

            print("Internal note hidden from requester: PASS")

            # 12. Forged internal-note requests are rejected.
            response = post_with_csrf(
                requester_client,
                f"/tickets/{ticket_id}/comment",
                {
                    "message": "Forged internal note attempt.",
                    "is_internal": "1",
                },
                follow_redirects=False,
            )

            assert response.status_code == 403

            print("Forged internal note rejected: PASS")

            # 13. Verify audit-history records.
            history_fields = {
                entry.field_name
                for entry in TicketHistory.query.filter_by(
                    ticket_id=ticket_id
                ).all()
            }

            expected_fields = {
                "created",
                "status",
                "priority",
                "assignee",
                "comment",
            }

            missing = expected_fields - history_fields

            assert not missing, (
                "Missing audit history: "
                + ", ".join(sorted(missing))
            )

            print("Ticket audit history: PASS")

            # 14. Verify the administrator's detail page.
            response = admin_client.get(
                f"/tickets/{ticket_id}"
            )

            assert response.status_code == 200
            assert b"Assign Technician" in response.data
            assert b"Recent History" in response.data

            print("Administrator ticket detail page: PASS")

        finally:
            db.session.rollback()

            # Cleanup is limited to the dedicated accounts and the ticket
            # created during this test run.
            if users_created:
                cleanup_test_data(ticket_id, usernames)

    print("\nAll ticket workflow tests completed successfully.")


if __name__ == "__main__":
    run_tests()
