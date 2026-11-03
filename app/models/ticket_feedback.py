from datetime import datetime, timezone

from app import db


class TicketFeedback(db.Model):
    """Feedback submitted after a ticket is resolved."""

    __tablename__ = "ticket_feedback"

    id = db.Column(db.Integer, primary_key=True)

    ticket_id = db.Column(
        db.Integer,
        db.ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    rating = db.Column(
        db.SmallInteger,
        nullable=False,
    )

    comments = db.Column(
        db.Text,
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    ticket = db.relationship(
        "Ticket",
        backref=db.backref(
            "feedback",
            uselist=False,
            cascade="all, delete-orphan",
        ),
    )

    user = db.relationship(
        "User",
        backref=db.backref("submitted_feedback", lazy="select"),
    )

    def __repr__(self):
        return f"<TicketFeedback {self.id}: rating={self.rating}>"