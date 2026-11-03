"""SLA status and historical compliance calculations for IntelliDesk."""

from datetime import datetime, timezone


COMPLETED_STATUSES = {"resolved", "closed"}

DEFAULT_SLA_HOURS = 24
APPROACHING_THRESHOLD = 0.25


def utc_now():
    """Return the current UTC time as a naive datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_datetime(value):
    """Normalize datetimes to naive UTC for MySQL DATETIME compatibility."""
    if value is None:
        return None

    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    return value


def get_sla_status(ticket, now=None):
    """Calculate the current SLA state of a ticket.

    Possible status values:
        within_sla
        approaching
        overdue
        completed
        no_deadline

    Historical compliance is calculated separately by get_sla_summary().
    """
    ticket_status = getattr(ticket, "status", None)

    if ticket_status in COMPLETED_STATUSES:
        return {
            "status": "completed",
            "label": "Completed",
            "remaining_seconds": None,
            "remaining_percent": None,
        }

    due_at = normalize_datetime(getattr(ticket, "due_at", None))

    if due_at is None:
        return {
            "status": "no_deadline",
            "label": "No deadline",
            "remaining_seconds": None,
            "remaining_percent": None,
        }

    current_time = (
        normalize_datetime(now) if now is not None else utc_now()
    )

    created_at = normalize_datetime(
        getattr(ticket, "created_at", None)
    )

    remaining_seconds = (due_at - current_time).total_seconds()

    if remaining_seconds <= 0:
        return {
            "status": "overdue",
            "label": "Overdue",
            "remaining_seconds": remaining_seconds,
            "remaining_percent": 0.0,
        }

    if created_at is not None:
        total_seconds = (due_at - created_at).total_seconds()
    else:
        total_seconds = DEFAULT_SLA_HOURS * 60 * 60

    if total_seconds <= 0:
        remaining_percent = 0.0
    else:
        remaining_percent = (
            remaining_seconds / total_seconds
        ) * 100.0

    if remaining_percent <= APPROACHING_THRESHOLD * 100:
        return {
            "status": "approaching",
            "label": "Approaching deadline",
            "remaining_seconds": remaining_seconds,
            "remaining_percent": remaining_percent,
        }

    return {
        "status": "within_sla",
        "label": "Within SLA",
        "remaining_seconds": remaining_seconds,
        "remaining_percent": remaining_percent,
    }


def get_sla_summary(tickets, now=None):
    """Summarize current SLA health and historical compliance.

    Historical compliance includes:
        - Completed tickets with both due_at and resolved_at.
        - Tickets are compliant only when resolved_at <= due_at.

    Tickets without sufficient historical data are excluded from the
    historical compliance denominator.

    Current health is reported separately from historical compliance.
    """
    summary = {
        "total": 0,
        "within_sla": 0,
        "approaching": 0,
        "overdue": 0,
        "completed": 0,
        "no_deadline": 0,
        "current_health_percent": None,
        "historical_compliance_percent": None,
        "historical_compliance_eligible": 0,
        "historical_compliance_met": 0,
        "historical_compliance_breached": 0,
        "historical_compliance_unknown": 0,
    }

    for ticket in tickets:
        result = get_sla_status(ticket, now=now)

        summary["total"] += 1
        summary[result["status"]] += 1

        ticket_status = getattr(ticket, "status", None)
        due_at = normalize_datetime(
            getattr(ticket, "due_at", None)
        )
        resolved_at = normalize_datetime(
            getattr(ticket, "resolved_at", None)
        )

        if ticket_status in COMPLETED_STATUSES:
            if due_at is None or resolved_at is None:
                summary["historical_compliance_unknown"] += 1
                continue

            summary["historical_compliance_eligible"] += 1

            if resolved_at <= due_at:
                summary["historical_compliance_met"] += 1
            else:
                summary["historical_compliance_breached"] += 1

    # Current operational health:
    # Among tickets with a deadline, count non-overdue tickets,
    # including completed tickets.
    current_eligible = (
        summary["within_sla"]
        + summary["approaching"]
        + summary["overdue"]
        + summary["completed"]
    )

    current_healthy = (
        summary["within_sla"]
        + summary["approaching"]
        + summary["completed"]
    )

    if current_eligible:
        summary["current_health_percent"] = round(
            current_healthy / current_eligible * 100.0,
            1,
        )

    # Historical compliance is based only on completed tickets
    # with both a deadline and a recorded resolution timestamp.
    if summary["historical_compliance_eligible"]:
        summary["historical_compliance_percent"] = round(
            summary["historical_compliance_met"]
            / summary["historical_compliance_eligible"]
            * 100.0,
            1,
        )

    return summary