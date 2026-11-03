"""Verify IntelliDesk dashboards and role-specific SLA visibility."""

from datetime import datetime, timedelta, timezone

from app import create_app, db
from app.models import Category, Ticket, User


TEST_USERNAMES = (
    "nova_dash_sla_user",
    "nova_dash_sla_technician",
    "nova_dash_sla_admin",
)

TEST_TICKET_NUMBER = "NOVA-DASH-SLA-01"
TEST_PASSWORD = "Temporary-Test-Password-482!"


def create_user(username, role):
    user = User(
        username=username,
        email=f"{username}@example.test",
        full_name=f"Dashboard SLA {role.title()}",
        role=role,
        is_active=True,
    )
    user.set_password(TEST_PASSWORD)
    db.session.add(user)
    db.session.flush()
    return user


def cleanup_test_data():
    ticket = Ticket.query.filter_by(
        ticket_number=TEST_TICKET_NUMBER
    ).first()

    if ticket:
        db.session.delete(ticket)
        db.session.flush()

    users = User.query.filter(
        User.username.in_(TEST_USERNAMES)
    ).all()

    for user in users:
        db.session.delete(user)

    db.session.commit()


def test_role_dashboard(username, role, expected_heading):
    """Test a role using its own fresh Flask application."""

    app = create_app()
    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
    )

    with app.app_context():
        account = User.query.filter_by(username=username).first()

        assert account is not None, (
            f"Test account {username} was not found."
        )

        client = app.test_client()

        login_response = client.post(
            "/auth/login",
            data={
                "username_or_email": username,
                "password": TEST_PASSWORD,
            },
            follow_redirects=False,
        )

        assert login_response.status_code == 302
        assert login_response.headers.get("Location") == "/dashboard/"

        with client.session_transaction() as session:
            session_user_id = session.get("_user_id")

        assert session_user_id == str(account.id), (
            f"{role} session verification failed. "
            f"Expected {account.id}, received {session_user_id}."
        )

        print(f"{role.title()} authentication: PASS")

        response = client.get("/dashboard/")
        body = response.get_data(as_text=True)

        assert response.status_code == 200
        assert expected_heading in body, (
            f"Expected '{expected_heading}' for {role}."
        )

        print(f"{role.title()} dashboard rendering: PASS")

        return body


def main():
    setup_app = create_app()
    setup_app.config.update(TESTING=True)

    with setup_app.app_context():

        if db.engine.url.database != "intellidesk":
            raise RuntimeError(
                "Safety check failed. Refusing to test another database."
            )

        try:
            # Remove leftovers from a previous interrupted test.
            cleanup_test_data()

            # Create temporary accounts.
            user = create_user(
                "nova_dash_sla_user",
                "user",
            )

            technician = create_user(
                "nova_dash_sla_technician",
                "technician",
            )

            admin = create_user(
                "nova_dash_sla_admin",
                "admin",
            )

            category = Category.query.filter_by(
                is_active=True
            ).first()

            assert category is not None, (
                "No active category exists for the test."
            )

            # Create an overdue ticket so it appears in the SLA dashboard.
            now = datetime.now(timezone.utc).replace(tzinfo=None)

            ticket = Ticket(
                ticket_number=TEST_TICKET_NUMBER,
                title="Temporary dashboard SLA test",
                description="Temporary ticket for dashboard verification.",
                status="open",
                priority="medium",
                requester_id=user.id,
                assignee_id=technician.id,
                category_id=category.id,
                due_at=now - timedelta(hours=1),
                created_at=now - timedelta(hours=2),
            )

            db.session.add(ticket)
            db.session.commit()

            print("Dashboard test accounts created: PASS")
            print("Dashboard SLA test ticket created: PASS")

            # Public dashboard.
            public_client = setup_app.test_client()
            public_response = public_client.get("/dashboard/")
            public_body = public_response.get_data(as_text=True)

            assert public_response.status_code == 200
            assert "Welcome to IntelliDesk" in public_body

            print("Public dashboard rendering: PASS")

            # Regular user dashboard.
            test_role_dashboard(
                "nova_dash_sla_user",
                "user",
                "My Dashboard",
            )

            # Technician dashboard.
            technician_body = test_role_dashboard(
                "nova_dash_sla_technician",
                "technician",
                "Technician Dashboard",
            )

            assert TEST_TICKET_NUMBER in technician_body, (
                "Technician cannot see the assigned overdue ticket."
            )

            print("Technician assigned-ticket visibility: PASS")

            # Administrator dashboard.
            test_role_dashboard(
                "nova_dash_sla_admin",
                "admin",
                "Administrator Dashboard",
            )

            print("\nAll dashboard SLA tests passed.")

        finally:
            db.session.rollback()
            cleanup_test_data()
            print("Dashboard SLA test data cleanup: PASS")


if __name__ == "__main__":
    main()
