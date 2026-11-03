"""Read-only IntelliDesk application performance baseline."""

import statistics
import time

from app import create_app, db
from app.models import Category, KnowledgeArticle, Ticket, User
from app.services.knowledge_recommendations import (
    recommend_knowledge_articles,
)
from app.services.similar_tickets import find_similar_tickets
from ml.predict_category import (
    load_model as load_category_model,
    predict_category,
)
from ml.predict_priority import (
    load_model as load_priority_model,
    predict_priority,
)


# ------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------

SAMPLE_TITLE = "Office Wi-Fi connection keeps disconnecting"

SAMPLE_DESCRIPTION = (
    "The office laptop repeatedly disconnects from the wireless "
    "network and cannot maintain a stable internet connection."
)

ROLES = {
    "user": "vp17",
    "technician": "dns12",
    "admin": "admin",
}


# ------------------------------------------------------------
# TIMING UTILITIES
# ------------------------------------------------------------

def measure(label, function, repetitions=5):
    """Measure an operation without changing application data."""

    durations = []

    for _ in range(repetitions):
        start = time.perf_counter()
        function()
        elapsed = (time.perf_counter() - start) * 1000
        durations.append(elapsed)

    average = statistics.mean(durations)
    median = statistics.median(durations)
    minimum = min(durations)
    maximum = max(durations)

    print(
        f"{label:<38} "
        f"avg={average:8.2f} ms | "
        f"median={median:8.2f} ms | "
        f"min={minimum:8.2f} ms | "
        f"max={maximum:8.2f} ms"
    )

    return {
        "label": label,
        "average": average,
        "median": median,
        "minimum": minimum,
        "maximum": maximum,
    }


# ------------------------------------------------------------
# APPLICATION INITIALIZATION
# ------------------------------------------------------------

print("\n========== INTELLIDESK PERFORMANCE BASELINE ==========\n")

startup_start = time.perf_counter()
app = create_app()
startup_ms = (time.perf_counter() - startup_start) * 1000

print(f"Application factory startup: {startup_ms:.2f} ms")

app.config.update(
    TESTING=True,
    WTF_CSRF_ENABLED=False,
    LOGIN_DISABLED=False,
)

results = []


# ------------------------------------------------------------
# BENCHMARK EXECUTION
# ------------------------------------------------------------

with app.app_context():

    print("\n========== DATABASE SAFETY CHECK ==========\n")

    database_name = db.session.execute(
        db.text("SELECT DATABASE()")
    ).scalar()

    print(f"Connected database: {database_name}")

    if database_name != "intellidesk":
        raise RuntimeError(
            "Safety check failed: expected intellidesk database."
        )

    print("Database safety check: PASS")

    print("\n========== DATABASE QUERY BENCHMARKS ==========\n")

    results.append(
        measure(
            "Database SELECT 1",
            lambda: db.session.execute(
                db.text("SELECT 1")
            ).scalar(),
        )
    )

    results.append(
        measure(
            "Ticket count",
            lambda: Ticket.query.count(),
        )
    )

    results.append(
        measure(
            "Active user lookup",
            lambda: User.query.filter_by(
                is_active=True
            ).all(),
        )
    )

    results.append(
        measure(
            "Published article retrieval",
            lambda: KnowledgeArticle.query.filter_by(
                is_published=True
            ).all(),
        )
    )

    print("\n========== RECOMMENDATION BENCHMARKS ==========\n")

    tickets = (
        Ticket.query
        .filter(Ticket.status != "closed")
        .order_by(Ticket.created_at.desc())
        .limit(2000)
        .all()
    )

    results.append(
        measure(
            "Knowledge recommendations",
            lambda: recommend_knowledge_articles(
                SAMPLE_TITLE,
                SAMPLE_DESCRIPTION,
                limit=3,
                min_similarity=0.08,
            ),
            repetitions=5,
        )
    )

    results.append(
        measure(
            "Similar-ticket recommendations",
            lambda: find_similar_tickets(
                SAMPLE_TITLE,
                SAMPLE_DESCRIPTION,
                tickets,
                limit=3,
                min_similarity=0.10,
            ),
            repetitions=5,
        )
    )

    print("\n========== MACHINE LEARNING BENCHMARKS ==========\n")

    # Clear caches so the first measurement includes model loading.
    load_category_model.cache_clear()
    load_priority_model.cache_clear()

    results.append(
        measure(
            "Category prediction (initial load)",
            lambda: predict_category(
                SAMPLE_TITLE,
                SAMPLE_DESCRIPTION,
            ),
            repetitions=1,
        )
    )

    results.append(
        measure(
            "Category prediction (cached)",
            lambda: predict_category(
                SAMPLE_TITLE,
                SAMPLE_DESCRIPTION,
            ),
            repetitions=10,
        )
    )

    results.append(
        measure(
            "Priority prediction (initial load)",
            lambda: predict_priority(
                SAMPLE_TITLE,
                SAMPLE_DESCRIPTION,
            ),
            repetitions=1,
        )
    )

    results.append(
        measure(
            "Priority prediction (cached)",
            lambda: predict_priority(
                SAMPLE_TITLE,
                SAMPLE_DESCRIPTION,
            ),
            repetitions=10,
        )
    )

    print("\n========== HTTP RESPONSE BENCHMARKS ==========\n")

    client = app.test_client()

    def benchmark_public_dashboard():
        response = client.get("/dashboard/")
        assert response.status_code == 200

    results.append(
        measure(
            "Public dashboard",
            benchmark_public_dashboard,
        )
    )

    def benchmark_role_dashboard(username, password):
        with client.session_transaction() as session:
            session.clear()

        response = client.post(
            "/auth/login",
            data={
                "username_or_email": username,
                "password": password,
            },
            follow_redirects=True,
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"Login benchmark failed for {username}: "
                f"HTTP {response.status_code}"
            )

        dashboard_response = client.get("/dashboard/")

        if dashboard_response.status_code != 200:
            raise RuntimeError(
                f"Dashboard failed for {username}: "
                f"HTTP {dashboard_response.status_code}"
            )

        return dashboard_response

    # Avoid retrieving or printing credentials.
    # This benchmark uses password verification only if a dedicated
    # benchmark password is explicitly supplied through environment vars.
    import os

    benchmark_password = os.getenv("NOVA_BENCHMARK_PASSWORD")

    if benchmark_password:
        print(
            "Role-based dashboard login benchmark enabled "
            "(password is not displayed)."
        )

        for role, username in ROLES.items():
            results.append(
                measure(
                    f"{role.title()} dashboard",
                    lambda u=username: benchmark_role_dashboard(
                        u,
                        benchmark_password,
                    ),
                    repetitions=3,
                )
            )

    else:
        print(
            "Role-based login benchmarks skipped: "
            "NOVA_BENCHMARK_PASSWORD is not configured."
        )

    print("\n========== ANONYMOUS ROUTE BENCHMARKS ==========\n")

    # These endpoints require authentication, so anonymous requests
    # only measure the authentication redirect and do not access data.
    for label, path in (
        ("Ticket list auth redirect", "/tickets/"),
        ("Knowledge list auth redirect", "/knowledge/"),
    ):
        results.append(
            measure(
                label,
                lambda p=path: client.get(p),
            )
        )

    db.session.remove()


# ------------------------------------------------------------
# SUMMARY
# ------------------------------------------------------------

print("\n========== BENCHMARK SUMMARY ==========\n")

print(f"Application startup: {startup_ms:.2f} ms")
print(f"Measurements collected: {len(results)}")

print(
    "\nNote: These measurements are local development "
    "baselines, not production load-test results."
)

print(
    "No application records were intentionally created, "
    "updated, or deleted."
)

print("\nPERFORMANCE BASELINE COMPLETED.")
