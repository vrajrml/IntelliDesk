from datetime import datetime, timezone

from app import db


class Ticket(db.Model):
    """Service request submitted through IntelliDesk."""

    __tablename__ = "tickets"

    id = db.Column(db.Integer, primary_key=True)

    ticket_number = db.Column(
        db.String(20),
        unique=True,
        nullable=False,
        index=True,
    )

    title = db.Column(
        db.String(200),
        nullable=False,
    )

    description = db.Column(
        db.Text,
        nullable=False,
    )

    status = db.Column(
        db.Enum(
            "open",
            "in_progress",
            "waiting_for_user",
            "resolved",
            "closed",
            name="ticket_status",
        ),
        nullable=False,
        default="open",
        index=True,
    )

    priority = db.Column(
        db.Enum(
            "low",
            "medium",
            "high",
            "critical",
            name="ticket_priority",
        ),
        nullable=False,
        default="medium",
        index=True,
    )

    # User who submitted the ticket.
    requester_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Technician assigned to handle the ticket.
    assignee_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Category assigned to the ticket.
    category_id = db.Column(
        db.Integer,
        db.ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # AI-generated recommendations, not automatically trusted decisions.
    predicted_category = db.Column(
        db.String(80),
        nullable=True,
    )

    predicted_priority = db.Column(
        db.String(20),
        nullable=True,
    )

    prediction_confidence = db.Column(
        db.Float,
        nullable=True,
    )

    # SLA tracking timestamps.
    due_at = db.Column(
        db.DateTime,
        nullable=True,
        index=True,
    )

    resolved_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships.
    requester = db.relationship(
        "User",
        foreign_keys=[requester_id],
        backref=db.backref("submitted_tickets", lazy="select"),
    )

    assignee = db.relationship(
        "User",
        foreign_keys=[assignee_id],
        backref=db.backref("assigned_tickets", lazy="select"),
    )

    category = db.relationship(
        "Category",
        back_populates="tickets",
    )

    comments = db.relationship(
        "TicketComment",
        back_populates="ticket",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self):
        return f"<Ticket {self.ticket_number}: {self.title}>"