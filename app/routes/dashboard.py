from flask import Blueprint, render_template
from flask_login import current_user, login_required

from app import db
from app.models import Ticket
from app.services.sla import get_sla_status, get_sla_summary


dashboard_bp = Blueprint(
    "dashboard",
    __name__,
    url_prefix="/dashboard",
)


ACTIVE_STATUSES = (
    "open",
    "in_progress",
    "waiting_for_user",
)


def get_dashboard_sla_data(query):
    """Build SLA metrics and deadline lists for an authorized ticket query."""
    tickets = query.order_by(Ticket.created_at.desc()).all()

    summary = get_sla_summary(tickets)

    overdue_tickets = []
    approaching_tickets = []

    for ticket in tickets:
        result = get_sla_status(ticket)

        if result["status"] == "overdue":
            overdue_tickets.append({
                "ticket": ticket,
                "sla": result,
            })
        elif result["status"] == "approaching":
            approaching_tickets.append({
                "ticket": ticket,
                "sla": result,
            })

    return {
        "sla_summary": summary,
        "overdue_tickets": overdue_tickets[:10],
        "approaching_tickets": approaching_tickets[:10],
    }


@dashboard_bp.route("/")
def index():
    """Display the dashboard appropriate for the current user's role."""

    if not current_user.is_authenticated:
        return render_template("dashboard/public.html")

    if current_user.role == "admin":
        data = get_dashboard_sla_data(Ticket.query)

        return render_template(
            "dashboard/admin.html",
            **data,
        )

    if current_user.role == "technician":
        # Technicians see tickets assigned to them in their personal
        # deadline lists, rather than unrelated staff tickets.
        assigned_query = Ticket.query.filter_by(
            assignee_id=current_user.id,
        )

        data = get_dashboard_sla_data(assigned_query)

        return render_template(
            "dashboard/technician.html",
            **data,
        )

    # Regular users see only their own ticket counts and SLA data.
    user_query = Ticket.query.filter_by(
        requester_id=current_user.id,
    )

    ticket_counts = {
        "open": user_query.filter_by(status="open").count(),
        "in_progress": user_query.filter_by(status="in_progress").count(),
        "resolved": user_query.filter_by(status="resolved").count(),
    }

    data = get_dashboard_sla_data(user_query)

    return render_template(
        "dashboard/user.html",
        ticket_counts=ticket_counts,
        **data,
    )
