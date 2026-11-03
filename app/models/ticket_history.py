from datetime import datetime, timezone

from app import db


class TicketHistory(db.Model):
    """Audit record describing a change to a ticket."""

    __tablename__ = "ticket_history"

    id = db.Column(db.Integer, primary_key=True)

    ticket_id = db.Column(
        db.Integer,
        db.ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    changed_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    field_name = db.Column(
        db.String(80),
        nullable=False,
    )

    old_value = db.Column(
        db.Text,
        nullable=True,
    )

    new_value = db.Column(
        db.Text,
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    ticket = db.relationship(
        "Ticket",
        backref=db.backref("history", lazy="select"),
    )

    changed_by = db.relationship(
        "User",
        backref=db.backref("ticket_changes", lazy="select"),
    )

    def __repr__(self):
        return f"<TicketHistory {self.id}: {self.field_name}>"