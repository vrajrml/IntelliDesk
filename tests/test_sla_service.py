"""Manual unit tests for IntelliDesk SLA calculations."""

from datetime import datetime, timedelta
from types import SimpleNamespace

from app.services.sla import get_sla_status, get_sla_summary


NOW = datetime(2026, 11, 2, 12, 0, 0)


def make_ticket(
    status="open",
    created_at=None,
    due_at=None,
    resolved_at=None,
):
    """Create an in-memory ticket without database access."""
    return SimpleNamespace(
        status=status,
        created_at=created_at,
        due_at=due_at,
        resolved_at=resolved_at,
    )


def test_within_sla():
    ticket = make_ticket(
        created_at=NOW - timedelta(hours=12),
        due_at=NOW + timedelta(hours=12),
    )

    result = get_sla_status(ticket, now=NOW)

    assert result["status"] == "within_sla"
    assert result["remaining_seconds"] == 12 * 60 * 60


def test_approaching_deadline():
    ticket = make_ticket(
        created_at=NOW - timedelta(hours=20),
        due_at=NOW + timedelta(hours=4),
    )

    result = get_sla_status(ticket, now=NOW)

    assert result["status"] == "approaching"


def test_overdue_ticket():
    ticket = make_ticket(
        created_at=NOW - timedelta(hours=30),
        due_at=NOW - timedelta(hours=6),
    )

    result = get_sla_status(ticket, now=NOW)

    assert result["status"] == "overdue"
    assert result["remaining_seconds"] < 0


def test_completed_ticket():
    for status in ("resolved", "closed"):
        ticket = make_ticket(
            status=status,
            created_at=NOW - timedelta(hours=12),
            due_at=NOW - timedelta(hours=2),
            resolved_at=NOW - timedelta(hours=1),
        )

        assert get_sla_status(ticket, now=NOW)["status"] == "completed"


def test_missing_deadline():
    ticket = make_ticket(
        created_at=NOW - timedelta(hours=1),
        due_at=None,
    )

    result = get_sla_status(ticket, now=NOW)

    assert result["status"] == "no_deadline"


def test_historical_compliance():
    created = NOW - timedelta(hours=12)
    due = NOW + timedelta(hours=12)

    met = make_ticket(
        status="resolved",
        created_at=created,
        due_at=due,
        resolved_at=due - timedelta(hours=1),
    )

    breached = make_ticket(
        status="closed",
        created_at=created,
        due_at=due,
        resolved_at=due + timedelta(hours=2),
    )

    unknown = make_ticket(
        status="resolved",
        created_at=created,
        due_at=None,
        resolved_at=NOW,
    )

    summary = get_sla_summary(
        [met, breached, unknown],
        now=NOW,
    )

    assert summary["historical_compliance_eligible"] == 2
    assert summary["historical_compliance_met"] == 1
    assert summary["historical_compliance_breached"] == 1
    assert summary["historical_compliance_unknown"] == 1
    assert summary["historical_compliance_percent"] == 50.0


def test_empty_summary():
    summary = get_sla_summary([], now=NOW)

    assert summary["total"] == 0
    assert summary["current_health_percent"] is None
    assert summary["historical_compliance_percent"] is None


def run_all_tests():
    tests = [
        test_within_sla,
        test_approaching_deadline,
        test_overdue_ticket,
        test_completed_ticket,
        test_missing_deadline,
        test_historical_compliance,
        test_empty_summary,
    ]

    for test in tests:
        test()
        print(f"{test.__name__}: PASS")

    print(f"\nAll {len(tests)} SLA tests passed.")


if __name__ == "__main__":
    run_all_tests()