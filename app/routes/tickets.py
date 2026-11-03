import secrets
from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import or_

from app import db
from app.models import (
    Category,
    Ticket,
    TicketComment,
    TicketHistory,
    User,
)
from app.routes.decorators import roles_required
from app.services.knowledge_recommendations import (
    recommend_knowledge_articles,
)
from app.services.similar_tickets import find_similar_tickets
from app.services.sla import get_sla_status
from ml.predict_category import predict_category
from ml.predict_priority import predict_priority


tickets_bp = Blueprint("tickets", __name__, url_prefix="/tickets")


VALID_STATUSES = {
    "open",
    "in_progress",
    "waiting_for_user",
    "resolved",
    "closed",
}

VALID_PRIORITIES = {
    "low",
    "medium",
    "high",
    "critical",
}


def utc_now():
    """Return a naive UTC datetime for MySQL DATETIME columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def generate_ticket_number():
    """Generate a unique ticket number."""
    for _ in range(10):
        number = f"NOVA-{secrets.token_hex(4).upper()}"

        exists = Ticket.query.filter_by(
            ticket_number=number
        ).first()

        if not exists:
            return number

    raise RuntimeError("Unable to generate a unique ticket number.")


def get_authorized_ticket(ticket_id):
    """Return a ticket only if the current user may access it."""
    ticket = db.session.get(Ticket, ticket_id)

    if ticket is None:
        abort(404)

    is_requester = ticket.requester_id == current_user.id
    is_staff = current_user.role in {"technician", "admin"}

    if not is_requester and not is_staff:
        abort(403)

    return ticket


def record_history(ticket, field_name, old_value, new_value):
    """Add an audit entry for a ticket change."""
    db.session.add(
        TicketHistory(
            ticket_id=ticket.id,
            changed_by_id=current_user.id,
            field_name=field_name,
            old_value=(
                str(old_value)
                if old_value is not None
                else None
            ),
            new_value=(
                str(new_value)
                if new_value is not None
                else None
            ),
        )
    )


def save_or_rollback():
    """Commit pending changes and report whether the operation succeeded."""
    try:
        db.session.commit()
        return True

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Ticket operation failed.")
        return False


def get_knowledge_recommendations(title, description):
    """Get published Knowledge Base recommendations without blocking tickets."""
    try:
        return recommend_knowledge_articles(
            title,
            description,
            limit=3,
            min_similarity=0.08,
        )

    except Exception:
        current_app.logger.exception(
            "Knowledge Base article recommendations failed."
        )
        return []


def get_similar_ticket_recommendations(title, description):
    """Find similar tickets while respecting requester privacy."""
    candidate_query = Ticket.query.filter(
        Ticket.status != "closed"
    )

    # Regular users receive recommendations based only on their own tickets.
    # Technicians and administrators can compare tickets across the system.
    if current_user.role == "user":
        candidate_query = candidate_query.filter(
            Ticket.requester_id == current_user.id
        )

    candidates = (
        candidate_query
        .order_by(Ticket.created_at.desc())
        .limit(2000)
        .all()
    )

    return find_similar_tickets(
        title,
        description,
        candidates,
        limit=3,
        min_similarity=0.10,
    )


def render_ticket_form(
    categories,
    form_data=None,
    similar_tickets=None,
    similarity_checked=False,
    knowledge_recommendations=None,
    status=200,
):
    """Render the ticket form with optional recommendations."""
    return (
        render_template(
            "tickets/create.html",
            categories=categories,
            form_data=form_data or {},
            similar_tickets=similar_tickets or [],
            similarity_checked=similarity_checked,
            knowledge_recommendations=(
                knowledge_recommendations or []
            ),
        ),
        status,
    )


# ============================================================
# TICKET LIST
# ============================================================

@tickets_bp.route("/")
@login_required
def list_tickets():
    """
    Display tickets according to the logged-in user's role.

    Users:
        See only tickets they submitted.

    Technicians:
        Can view all tickets for ticket-management purposes.

    Administrators:
        Can view all tickets across the system.
    """

    if current_user.role in {"admin", "technician"}:
        query = Ticket.query
    else:
        query = Ticket.query.filter_by(
            requester_id=current_user.id
        )

    # Search by ticket number, title, or description.
    search = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()

    if search:
        pattern = f"%{search}%"

        query = query.filter(
            or_(
                Ticket.ticket_number.like(pattern),
                Ticket.title.like(pattern),
                Ticket.description.like(pattern),
            )
        )

    # Apply the status filter only for valid status values.
    if status in VALID_STATUSES:
        query = query.filter_by(status=status)

    tickets = (
        query
        .order_by(Ticket.created_at.desc())
        .all()
    )

    return render_template(
        "tickets/list.html",
        tickets=tickets,
        search=search,
        selected_status=status,
    )


# ============================================================
# CREATE TICKET
# ============================================================

@tickets_bp.route("/new", methods=["GET", "POST"])
@login_required
@roles_required("user", "technician", "admin")
def create_ticket():
    """Create tickets with advisory AI and Knowledge Base recommendations."""

    categories = (
        Category.query
        .filter_by(is_active=True)
        .order_by(Category.name)
        .all()
    )

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get(
            "description", ""
        ).strip()
        category_id = request.form.get(
            "category_id", ""
        ).strip()
        action = request.form.get(
            "action", "create_ticket"
        ).strip()

        errors = []

        if not title or len(title) > 200:
            errors.append(
                "Title must contain between 1 and 200 characters."
            )

        if len(description) < 10 or len(description) > 10000:
            errors.append(
                "Description must contain between 10 and 10,000 characters."
            )

        category = None

        try:
            category = Category.query.filter_by(
                id=int(category_id),
                is_active=True,
            ).first()

        except (TypeError, ValueError):
            pass

        if category is None:
            errors.append(
                "Select a valid, active category."
            )

        if errors:
            for error in errors:
                flash(error, "danger")

            return render_ticket_form(
                categories=categories,
                form_data=request.form,
                status=400,
            )

        # Recommendations are advisory and must never prevent submission.
        knowledge_recommendations = (
            get_knowledge_recommendations(
                title,
                description,
            )
        )

        # Allow users to preview similar tickets without creating a record.
        if action == "find_similar":
            similar_tickets = []

            try:
                similar_tickets = (
                    get_similar_ticket_recommendations(
                        title,
                        description,
                    )
                )

            except Exception:
                current_app.logger.exception(
                    "Similar-ticket detection failed."
                )

                flash(
                    "Similar tickets could not be checked. "
                    "You can still submit your ticket.",
                    "warning",
                )

            return render_ticket_form(
                categories=categories,
                form_data=request.form,
                similar_tickets=similar_tickets,
                similarity_checked=True,
                knowledge_recommendations=(
                    knowledge_recommendations
                ),
            )

        # Predict the category independently.
        category_prediction = None

        try:
            category_prediction = predict_category(
                title,
                description,
            )

        except Exception:
            current_app.logger.exception(
                "Category prediction failed. "
                "Ticket creation will continue without this recommendation."
            )

        # Predict the priority independently.
        priority_prediction = None

        try:
            priority_prediction = predict_priority(
                title,
                description,
            )

        except Exception:
            current_app.logger.exception(
                "Priority prediction failed. "
                "Ticket creation will continue without this recommendation."
            )

        # Predictions remain advisory.
        # The selected category is preserved and priority defaults to medium.
        ticket = Ticket(
            ticket_number=generate_ticket_number(),
            title=title,
            description=description,
            requester_id=current_user.id,
            category_id=category.id,
            predicted_category=(
                category_prediction["category"]
                if category_prediction
                else None
            ),
            prediction_confidence=(
                category_prediction["confidence"]
                if category_prediction
                else None
            ),
            predicted_priority=(
                priority_prediction["priority"]
                if priority_prediction
                else None
            ),
            status="open",
            priority="medium",
            due_at=utc_now() + timedelta(hours=24),
        )

        try:
            db.session.add(ticket)
            db.session.flush()

            record_history(
                ticket,
                "created",
                None,
                "Ticket created",
            )

            db.session.commit()

        except Exception:
            db.session.rollback()

            current_app.logger.exception(
                "Ticket creation failed."
            )

            flash(
                "We couldn't create your ticket. Please try again.",
                "danger",
            )

            return render_ticket_form(
                categories=categories,
                form_data=request.form,
                status=500,
            )

        flash(
            f"Ticket {ticket.ticket_number} was created successfully.",
            "success",
        )

        return redirect(
            url_for(
                "tickets.ticket_detail",
                ticket_id=ticket.id,
            )
        )

    return render_ticket_form(
        categories=categories,
        form_data={},
    )


# ============================================================
# TICKET DETAILS
# ============================================================

@tickets_bp.route("/<int:ticket_id>")
@login_required
def ticket_detail(ticket_id):
    """Display a ticket and its visible comments."""

    ticket = get_authorized_ticket(ticket_id)

    technicians = []

    if current_user.role == "admin":
        technicians = (
            User.query
            .filter_by(
                role="technician",
                is_active=True,
            )
            .order_by(User.full_name)
            .all()
        )

    sla_status = get_sla_status(ticket)

    return render_template(
        "tickets/detail.html",
        ticket=ticket,
        technicians=technicians,
        sla_status=sla_status,
    )


# ============================================================
# UPDATE TICKET STATUS AND PRIORITY
# ============================================================

@tickets_bp.route(
    "/<int:ticket_id>/update",
    methods=["POST"],
)
@login_required
@roles_required("technician", "admin")
def update_ticket(ticket_id):
    """Update a ticket's status and priority."""

    ticket = db.session.get(Ticket, ticket_id)

    if ticket is None:
        abort(404)

    new_status = request.form.get(
        "status", ""
    ).strip()
    new_priority = request.form.get(
        "priority", ""
    ).strip()

    if new_status not in VALID_STATUSES:
        flash(
            "Select a valid ticket status.",
            "danger",
        )

        return redirect(
            url_for(
                "tickets.ticket_detail",
                ticket_id=ticket.id,
            )
        )

    if new_priority not in VALID_PRIORITIES:
        flash(
            "Select a valid ticket priority.",
            "danger",
        )

        return redirect(
            url_for(
                "tickets.ticket_detail",
                ticket_id=ticket.id,
            )
        )

    old_status = ticket.status
    old_priority = ticket.priority

    if old_status != new_status:
        record_history(
            ticket,
            "status",
            old_status,
            new_status,
        )

        ticket.status = new_status

        if new_status == "resolved":
            ticket.resolved_at = utc_now()

        elif old_status == "resolved":
            ticket.resolved_at = None

    if old_priority != new_priority:
        record_history(
            ticket,
            "priority",
            old_priority,
            new_priority,
        )

        ticket.priority = new_priority

    if not save_or_rollback():
        flash(
            "The ticket could not be updated.",
            "danger",
        )

    elif (
        old_status != new_status
        or old_priority != new_priority
    ):
        flash(
            "Ticket updated successfully.",
            "success",
        )

    else:
        flash(
            "No ticket changes were needed.",
            "info",
        )

    return redirect(
        url_for(
            "tickets.ticket_detail",
            ticket_id=ticket.id,
        )
    )


# ============================================================
# ASSIGN TICKET TO TECHNICIAN
# ============================================================

@tickets_bp.route(
    "/<int:ticket_id>/assign",
    methods=["POST"],
)
@login_required
@roles_required("admin")
def assign_ticket(ticket_id):
    """Assign a ticket to an active technician. Admin only."""

    ticket = db.session.get(Ticket, ticket_id)

    if ticket is None:
        abort(404)

    assignee_value = request.form.get(
        "assignee_id", ""
    ).strip()

    new_assignee = None

    if assignee_value:
        try:
            assignee_id = int(assignee_value)

        except ValueError:
            flash(
                "Select a valid technician.",
                "danger",
            )

            return redirect(
                url_for(
                    "tickets.ticket_detail",
                    ticket_id=ticket.id,
                )
            )

        new_assignee = User.query.filter_by(
            id=assignee_id,
            role="technician",
            is_active=True,
        ).first()

        if new_assignee is None:
            flash(
                "The selected account is not an active technician.",
                "danger",
            )

            return redirect(
                url_for(
                    "tickets.ticket_detail",
                    ticket_id=ticket.id,
                )
            )

    old_assignee_id = ticket.assignee_id
    new_assignee_id = (
        new_assignee.id
        if new_assignee
        else None
    )

    if old_assignee_id == new_assignee_id:
        flash(
            "The ticket is already assigned that way.",
            "info",
        )

        return redirect(
            url_for(
                "tickets.ticket_detail",
                ticket_id=ticket.id,
            )
        )

    old_assignee = (
        db.session.get(User, old_assignee_id)
        if old_assignee_id is not None
        else None
    )

    record_history(
        ticket,
        "assignee",
        old_assignee.username if old_assignee else None,
        new_assignee.username if new_assignee else None,
    )

    ticket.assignee_id = new_assignee_id

    if not save_or_rollback():
        flash(
            "The ticket assignment could not be saved.",
            "danger",
        )

    else:
        flash(
            "Ticket assignment updated successfully.",
            "success",
        )

    return redirect(
        url_for(
            "tickets.ticket_detail",
            ticket_id=ticket.id,
        )
    )


# ============================================================
# ADD COMMENT OR INTERNAL NOTE
# ============================================================

@tickets_bp.route(
    "/<int:ticket_id>/comment",
    methods=["POST"],
)
@login_required
def add_comment(ticket_id):
    """Add a comment; only staff may create internal notes."""

    ticket = get_authorized_ticket(ticket_id)

    message = request.form.get(
        "message", ""
    ).strip()

    internal_value = request.form.get(
        "is_internal", ""
    ).strip()

    is_staff = current_user.role in {
        "technician",
        "admin",
    }

    is_internal = internal_value == "1"

    if is_internal and not is_staff:
        abort(403)

    if not message:
        flash(
            "Comment cannot be empty.",
            "danger",
        )

        return redirect(
            url_for(
                "tickets.ticket_detail",
                ticket_id=ticket.id,
            )
        )

    if len(message) > 5000:
        flash(
            "Comments cannot exceed 5,000 characters.",
            "danger",
        )

        return redirect(
            url_for(
                "tickets.ticket_detail",
                ticket_id=ticket.id,
            )
        )

    comment = TicketComment(
        ticket_id=ticket.id,
        user_id=current_user.id,
        message=message,
        is_internal=is_internal,
    )

    try:
        db.session.add(comment)

        record_history(
            ticket,
            "comment",
            None,
            (
                "Internal note added"
                if is_internal
                else "Comment added"
            ),
        )

        db.session.commit()

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Adding ticket comment failed."
        )

        flash(
            "Your comment could not be saved.",
            "danger",
        )

    else:
        flash(
            "Comment added successfully.",
            "success",
        )

    return redirect(
        url_for(
            "tickets.ticket_detail",
            ticket_id=ticket.id,
        )
    )