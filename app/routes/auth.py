from urllib.parse import urljoin, urlparse

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_user, logout_user
from sqlalchemy import or_
from werkzeug.security import check_password_hash

from app import db
from app.models import User


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def is_safe_redirect_target(target):
    """Allow redirects only to local URLs."""

    if not target:
        return False

    host_url = urlparse(request.host_url)
    redirect_url = urlparse(urljoin(request.host_url, target))

    return (
        redirect_url.scheme in {"http", "https"}
        and host_url.scheme == redirect_url.scheme
        and host_url.netloc == redirect_url.netloc
    )


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Register a standard IntelliDesk user account."""

    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        errors = []

        if not full_name or len(full_name) > 120:
            errors.append("Enter a name containing 1–120 characters.")

        if (
            not username
            or len(username) < 3
            or len(username) > 80
            or not username.replace("_", "").replace("-", "").isalnum()
        ):
            errors.append(
                "Username must be 3–80 characters and contain only "
                "letters, numbers, underscores, or hyphens."
            )

        if not email or len(email) > 120:
            errors.append("Enter a valid email address.")

        if len(password) < 8:
            errors.append("Password must contain at least 8 characters.")

        if password != confirm_password:
            errors.append("The passwords do not match.")

        if not errors:
            existing_user = db.session.query(User).filter(
                or_(
                    User.username == username,
                    User.email == email,
                )
            ).first()

            if existing_user:
                errors.append(
                    "That username or email address is already registered."
                )

        if errors:
            for error in errors:
                flash(error, "danger")

            return render_template("auth/register.html")

        user = User(
            full_name=full_name,
            username=username,
            email=email,
            role="user",
        )
        user.set_password(password)

        try:
            db.session.add(user)
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash(
                "Registration could not be completed. "
                "Please try again.",
                "danger",
            )
            return render_template("auth/register.html"), 500

        flash(
            "Your account has been created. You can now log in.",
            "success",
        )
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Authenticate an existing user."""

    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        username_or_email = request.form.get(
            "username_or_email", ""
        ).strip()

        password = request.form.get("password", "")

        user = db.session.query(User).filter(
            or_(
                User.username == username_or_email,
                User.email == username_or_email.lower(),
            )
        ).first()

        # Use a generic error to avoid revealing which accounts exist.
        if user is None or not user.check_password(password):
            flash("Invalid username/email or password.", "danger")
            return render_template("auth/login.html"), 401

        if not user.is_active:
            flash(
                "This account is inactive. Contact an administrator.",
                "danger",
            )
            return render_template("auth/login.html"), 403

        login_user(user)

        next_page = request.args.get("next")

        if next_page and is_safe_redirect_target(next_page):
            return redirect(next_page)

        return redirect(url_for("dashboard.index"))

    return render_template("auth/login.html")


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Log out the current user."""

    if current_user.is_authenticated:
        logout_user()
        flash("You have been logged out.", "success")

    return redirect(url_for("auth.login"))