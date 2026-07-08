from flask import Flask, jsonify

from app.config import Config
from app.extensions import db, login_manager, migrate


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    from app.cli import register_cli
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    register_blueprints(app)
    register_health_route(app)
    register_cli(app)

    return app


def register_blueprints(app):
    from app.attachments import bp as attachments_bp
    from app.auth import bp as auth_bp
    from app.dashboard import bp as dashboard_bp
    from app.issues import bp as issues_bp
    from app.projects import bp as projects_bp
    from app.reports import bp as reports_bp
    from app.users import bp as users_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(issues_bp)
    app.register_blueprint(attachments_bp)


def register_health_route(app):
    @app.get("/health")
    def health():
        return jsonify(status="ok")
