from datetime import datetime, timezone

from app import db


class Category(db.Model):
    """Category used to classify service requests."""

    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(
        db.String(80),
        unique=True,
        nullable=False,
    )

    description = db.Column(
        db.String(255),
        nullable=True,
    )

    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    tickets = db.relationship(
        "Ticket",
        back_populates="category",
        lazy="select",
    )

    def __repr__(self):
        return f"<Category {self.name}>"