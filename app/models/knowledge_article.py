from datetime import datetime, timezone

from app import db


class KnowledgeArticle(db.Model):
    """Knowledge-base article containing a solution or guide."""

    __tablename__ = "knowledge_articles"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(
        db.String(200),
        nullable=False,
        index=True,
    )

    slug = db.Column(
        db.String(220),
        unique=True,
        nullable=False,
    )

    summary = db.Column(
        db.String(500),
        nullable=False,
    )

    content = db.Column(
        db.Text,
        nullable=False,
    )

    category_id = db.Column(
        db.Integer,
        db.ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    author_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    is_published = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    view_count = db.Column(
        db.Integer,
        nullable=False,
        default=0,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    category = db.relationship(
        "Category",
        backref=db.backref("knowledge_articles", lazy="select"),
    )

    author = db.relationship(
        "User",
        backref=db.backref("knowledge_articles", lazy="select"),
    )

    def __repr__(self):
        return f"<KnowledgeArticle {self.slug}>"