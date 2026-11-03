from flask import Flask, redirect, url_for
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

from config import Config


db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_class=Config):
    """Create and configure the IntelliDesk application."""

    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    from app import models  # noqa: F401

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User

        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return None

        user = db.session.get(User, user_id)

        if user is None or not user.is_active:
            return None

        return user

    csrf.init_app(app)

    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.knowledge import knowledge_bp
    from app.routes.tickets import tickets_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(tickets_bp)
    app.register_blueprint(knowledge_bp)

    @app.get("/")
    def index():
        return redirect(url_for("dashboard.index"))

    @app.get("/health")
    def health():
        return {"status": "healthy"}

    return app