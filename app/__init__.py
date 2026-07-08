from flask import Flask, jsonify, redirect, request, url_for
from flask_login import current_user

from app.config import Config
from app.extensions import csrf, db, login_manager, migrate
from app.ui import register_template_helpers


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    if app.config.get("MAX_CONTENT_LENGTH") is None:
        app.config["MAX_CONTENT_LENGTH"] = int(app.config.get("MAX_UPLOAD_MB", 10)) * 1024 * 1024
    if app.config.get("APP_ENV") == "production":
        app.config["DEBUG"] = False

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "auth.login"

    from app.cli import register_cli
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    register_blueprints(app)
    register_health_route(app)
    register_auth_guard(app)
    register_template_helpers(app)
    register_cli(app)

    return app


def register_blueprints(app):
    from app.admin import bp as admin_bp
    from app.attachments import bp as attachments_bp
    from app.auth import bp as auth_bp
    from app.dashboard import api_bp as dashboard_api_bp
    from app.dashboard import bp as dashboard_bp
    from app.issues import bp as issues_bp
    from app.projects import bp as projects_bp
    from app.reports import bp as reports_bp
    from app.users import bp as users_bp

    app.register_blueprint(admin_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(dashboard_api_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(issues_bp)
    app.register_blueprint(attachments_bp)


def register_health_route(app):
    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.get("/")
    def index():
        return redirect(url_for("dashboard.index"))


def register_auth_guard(app):
    public_endpoints = {"auth.login", "health", "static"}

    @app.before_request
    def require_login():
        if request.endpoint in public_endpoints:
            return None

        if current_user.is_authenticated:
            return None

        return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
