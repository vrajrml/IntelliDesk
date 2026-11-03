"""Read-only authenticated page performance benchmark."""

import statistics
import time

from app import create_app, db
from app.models import User


ACCOUNTS = {
    "user": "vp17",
    "technician": "dns12",
    "admin": "admin",
}

REPETITIONS = 10


def measure(label, function):
    """Measure repeated HTTP requests."""

    timings = []

    # One warm-up request, excluded from measurements.
    response = function()

    if response.status_code != 200:
        raise RuntimeError(
            f"{label}: expected HTTP 200, "
            f"received HTTP {response.status_code}"
        )

    for _ in range(REPETITIONS):
        start = time.perf_counter()
        response = function()
        elapsed = (time.perf_counter() - start) * 1000

        if response.status_code != 200:
            raise RuntimeError(
                f"{label}: expected HTTP 200, "
                f"received HTTP {response.status_code}"
            )

        timings.append(elapsed)

    print(
        f"{label:<38}"
        f" median={statistics.median(timings):8.2f} ms |"
        f" avg={statistics.mean(timings):8.2f} ms |"
        f" min={min(timings):8.2f} ms |"
        f" max={max(timings):8.2f} ms"
    )


print("\n========== AUTHENTICATED PAGE BENCHMARK ==========\n")

app = create_app()

app.config.update(
    TESTING=True,
    WTF_CSRF_ENABLED=False,
)

with app.app_context():

    database_name = db.session.execute(
        db.text("SELECT DATABASE()")
    ).scalar()

    if database_name != "intellidesk":
        raise RuntimeError(
            "Safety check failed: wrong database."
        )

    print(f"Database: {database_name}")
    print("Database safety check: PASS")

    for role, username in ACCOUNTS.items():

        user = User.query.filter_by(
            username=username,
            role=role,
            is_active=True,
        ).first()

        if user is None:
            raise RuntimeError(
                f"Expected active {role} account not found."
            )

        client = app.test_client()

        # Authenticate the test client using the existing account.
        # No password is requested, accessed, or displayed.
        with client.session_transaction() as session:
            session["_user_id"] = str(user.id)
            session["_fresh"] = True

        print(f"\n========== {role.upper()} ==========")

        measure(
            f"{role.title()} dashboard",
            lambda: client.get("/dashboard/"),
        )

        measure(
            f"{role.title()} ticket list",
            lambda: client.get("/tickets/"),
        )

        measure(
            f"{role.title()} Knowledge Base",
            lambda: client.get("/knowledge/"),
        )

    db.session.remove()

print("\nAUTHENTICATED PAGE BENCHMARK COMPLETED.")
print("No application records were intentionally modified.")
