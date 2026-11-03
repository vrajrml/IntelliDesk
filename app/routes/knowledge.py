"""Knowledge base routes for IntelliDesk."""

import re

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
from app.models import Category, KnowledgeArticle
from app.routes.decorators import roles_required


knowledge_bp = Blueprint(
    "knowledge",
    __name__,
    url_prefix="/knowledge",
)


STAFF_ROLES = {"technician", "admin"}


def generate_slug(title, article_id=None):
    """Generate a URL-friendly, unique article slug."""
    base_slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    base_slug = base_slug[:180].strip("-") or "article"
    slug = base_slug
    suffix = 2

    while True:
        query = KnowledgeArticle.query.filter_by(slug=slug)

        if article_id is not None:
            query = query.filter(KnowledgeArticle.id != article_id)

        if query.first() is None:
            return slug

        slug = f"{base_slug}-{suffix}"
        suffix += 1


def get_active_categories():
    """Return active categories in alphabetical order."""
    return Category.query.filter_by(
        is_active=True
    ).order_by(Category.name.asc()).all()


def get_article_or_404(article_id):
    """Load an article while enforcing unpublished-article visibility."""
    article = db.session.get(KnowledgeArticle, article_id)

    if article is None:
        abort(404)

    if not article.is_published and current_user.role not in STAFF_ROLES:
        abort(404)

    return article


@knowledge_bp.route("/")
@login_required
def list_articles():
    """List published articles, with search and category filtering."""
    query = KnowledgeArticle.query.filter_by(is_published=True)

    search = request.args.get("q", "").strip()[:200]
    category_value = request.args.get("category", "").strip()

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                KnowledgeArticle.title.like(pattern),
                KnowledgeArticle.summary.like(pattern),
                KnowledgeArticle.content.like(pattern),
            )
        )

    selected_category = None

    if category_value:
        try:
            selected_category = int(category_value)
        except ValueError:
            selected_category = None

        if selected_category is not None:
            query = query.filter_by(category_id=selected_category)

    articles = query.order_by(
        KnowledgeArticle.updated_at.desc(),
        KnowledgeArticle.id.desc(),
    ).all()

    return render_template(
        "knowledge/list.html",
        articles=articles,
        categories=get_active_categories(),
        search=search,
        selected_category=selected_category,
    )


@knowledge_bp.route("/<int:article_id>")
@login_required
def article_detail(article_id):
    """Display an article and safely increment its view count."""
    article = get_article_or_404(article_id)

    try:
        article.view_count = (article.view_count or 0) + 1
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Unable to increment knowledge article view count."
        )

    return render_template(
        "knowledge/detail.html",
        article=article,
    )


@knowledge_bp.route("/new", methods=["GET", "POST"])
@login_required
@roles_required("technician", "admin")
def create_article():
    """Create a knowledge article."""
    categories = get_active_categories()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        summary = request.form.get("summary", "").strip()
        content = request.form.get("content", "").strip()
        category_value = request.form.get("category_id", "").strip()
        is_published = request.form.get("is_published") == "1"

        errors = []
        category = None

        if not title or len(title) > 200:
            errors.append("Title must contain between 1 and 200 characters.")

        if not summary or len(summary) > 500:
            errors.append("Summary must contain between 1 and 500 characters.")

        if not content or len(content) > 50000:
            errors.append(
                "Article content must contain between 1 and 50,000 characters."
            )

        if category_value:
            try:
                category = Category.query.filter_by(
                    id=int(category_value),
                    is_active=True,
                ).first()
            except ValueError:
                category = None

            if category is None:
                errors.append("Select a valid active category.")

        if errors:
            for error in errors:
                flash(error, "danger")

            return render_template(
                "knowledge/form.html",
                article=None,
                categories=categories,
                form_data=request.form,
                page_heading="Create Knowledge Article",
            ), 400

        article = KnowledgeArticle(
            title=title,
            slug=generate_slug(title),
            summary=summary,
            content=content,
            category_id=category.id if category else None,
            author_id=current_user.id,
            is_published=is_published,
        )

        try:
            db.session.add(article)
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception(
                "Knowledge article creation failed."
            )
            flash("Unable to create the article. Please try again.", "danger")

            return render_template(
                "knowledge/form.html",
                article=None,
                categories=categories,
                form_data=request.form,
                page_heading="Create Knowledge Article",
            ), 500

        flash("Knowledge article created successfully.", "success")

        return redirect(
            url_for("knowledge.article_detail", article_id=article.id)
        )

    return render_template(
        "knowledge/form.html",
        article=None,
        categories=categories,
        form_data={},
        page_heading="Create Knowledge Article",
    )


@knowledge_bp.route("/<int:article_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("technician", "admin")
def edit_article(article_id):
    """Edit an article; technicians can edit their own articles."""
    article = db.session.get(KnowledgeArticle, article_id)

    if article is None:
        abort(404)

    if (
        current_user.role != "admin"
        and article.author_id != current_user.id
    ):
        abort(403)

    categories = get_active_categories()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        summary = request.form.get("summary", "").strip()
        content = request.form.get("content", "").strip()
        category_value = request.form.get("category_id", "").strip()

        errors = []
        category = None

        if not title or len(title) > 200:
            errors.append("Title must contain between 1 and 200 characters.")

        if not summary or len(summary) > 500:
            errors.append("Summary must contain between 1 and 500 characters.")

        if not content or len(content) > 50000:
            errors.append(
                "Article content must contain between 1 and 50,000 characters."
            )

        if category_value:
            try:
                category = Category.query.filter_by(
                    id=int(category_value),
                    is_active=True,
                ).first()
            except ValueError:
                category = None

            if category is None:
                errors.append("Select a valid active category.")

        if errors:
            for error in errors:
                flash(error, "danger")

            return render_template(
                "knowledge/form.html",
                article=article,
                categories=categories,
                form_data=request.form,
                page_heading="Edit Knowledge Article",
            ), 400

        article.title = title
        article.slug = generate_slug(title, article_id=article.id)
        article.summary = summary
        article.content = content
        article.category_id = category.id if category else None

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception(
                "Knowledge article update failed."
            )
            flash("Unable to update the article. Please try again.", "danger")

            return render_template(
                "knowledge/form.html",
                article=article,
                categories=categories,
                form_data=request.form,
                page_heading="Edit Knowledge Article",
            ), 500

        flash("Knowledge article updated successfully.", "success")

        return redirect(
            url_for("knowledge.article_detail", article_id=article.id)
        )

    return render_template(
        "knowledge/form.html",
        article=article,
        categories=categories,
        form_data={
            "title": article.title,
            "summary": article.summary,
            "content": article.content,
            "category_id": (
                str(article.category_id)
                if article.category_id is not None
                else ""
            ),
            "is_published": "1" if article.is_published else "0",
        },
        page_heading="Edit Knowledge Article",
    )


@knowledge_bp.route("/<int:article_id>/publication", methods=["POST"])
@login_required
@roles_required("technician", "admin")
def toggle_publication(article_id):
    """Publish or unpublish an article."""
    article = db.session.get(KnowledgeArticle, article_id)

    if article is None:
        abort(404)

    if (
        current_user.role != "admin"
        and article.author_id != current_user.id
    ):
        abort(403)

    article.is_published = not article.is_published

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Knowledge article publication change failed."
        )
        flash("Unable to change publication status.", "danger")
    else:
        state = "published" if article.is_published else "unpublished"
        flash(f"Article {state} successfully.", "success")

    return redirect(
        url_for("knowledge.article_detail", article_id=article.id)
    )