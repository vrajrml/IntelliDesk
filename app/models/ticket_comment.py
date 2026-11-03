from datetime import datetime, timezone

from app import db


class TicketComment(db.Model):
    """Comment or update attached to a ticket."""

    __tablename__ = "ticket_comments"

    id = db.Column(db.Integer, primary_key=True)

    ticket_id = db.Column(
        db.Integer,
        db.ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    message = db.Column(
        db.Text,
        nullable=False,
    )

    is_internal = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    ticket = db.relationship(
        "Ticket",
        back_populates="comments",
    )

    author = db.relationship(
        "User",
        backref=db.backref("ticket_comments", lazy="select"),
    )

    def __repr__(self):
        return f"<TicketComment {self.id} on Ticket {self.ticket_id}>"