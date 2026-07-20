from flask import Flask, abort, jsonify, redirect, request, url_for
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import Config
from app.extensions import csrf, db, limiter, login_manager, migrate
from app.security import production_configuration_errors
from app.ui import register_template_helpers


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.config.setdefault("RATELIMIT_STORAGE_URI", "memory://")
    app.config.setdefault("RATELIMIT_LOGIN_LIMIT", "5 per minute")
    app.config.setdefault("RATELIMIT_EXPORT_LIMIT", "10 per hour")
    if app.config.get("MAX_CONTENT_LENGTH") is None:
        app.config["MAX_CONTENT_LENGTH"] = int(app.config.get("MAX_UPLOAD_MB", 10)) * 1024 * 1024
    configuration_errors = production_configuration_errors(app.config)
    if configuration_errors:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(configuration_errors))
    proxy_hops = int(app.config.get("TRUST_PROXY_HOPS", 0))
    if proxy_hops:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxy_hops, x_proto=proxy_hops, x_host=proxy_hops)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    login_manager.login_view = "auth.login"

    from app.cli import register_cli
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    register_blueprints(app)
    register_health_route(app)
    register_trusted_host_guard(app)
    register_auth_guard(app)
    register_security_headers(app)
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
    from app.modules import bp as modules_bp
    from app.partner_companies import bp as partner_companies_bp
    from app.partner_field_collections import bp as partner_field_collections_bp
    from app.partner_fields import bp as partner_fields_bp
    from app.partner_relations import bp as partner_relations_bp
    from app.partners import bp as partners_bp
    from app.projects import bp as projects_bp
    from app.reports import bp as reports_bp
    from app.users import bp as users_bp

    app.register_blueprint(admin_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(modules_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(dashboard_api_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(issues_bp)
    app.register_blueprint(attachments_bp)
    app.register_blueprint(partners_bp)
    app.register_blueprint(partner_companies_bp)
    app.register_blueprint(partner_fields_bp)
    app.register_blueprint(partner_field_collections_bp)
    app.register_blueprint(partner_relations_bp)


def register_health_route(app):
    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok")

    @app.get("/")
    def index():
        return redirect(url_for("dashboard.index"))


def register_auth_guard(app):
    public_endpoints = {"auth.login", "health", "healthz", "static"}

    @app.before_request
    def require_login():
        if request.endpoint in public_endpoints:
            return None

        if current_user.is_authenticated:
            return None

        return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))

    @app.before_request
    def require_reports_module_access():
        """Keep the report system behind its canonical module permission.

        Administration of users/roles remains reachable independently; only
        report project/category administration belongs to this module.
        """
        if not current_user.is_authenticated:
            return None
        endpoint = request.endpoint or ""
        report_endpoints = ("dashboard.", "dashboard_api.", "projects.", "reports.", "issues.", "attachments.")
        is_report_admin = endpoint in {
            "admin.projects_index", "admin.projects_new", "admin.projects_edit",
            "admin.projects_archive", "admin.projects_reporters", "admin.categories_index",
            "admin.categories_edit", "admin.categories_activate", "admin.categories_deactivate",
            "admin.categories_delete",
        }
        if endpoint.startswith(report_endpoints) or is_report_admin:
            from app.auth.permissions import REPORTS_MODULE_DENY_MESSAGE, can_access_reports_module
            if not can_access_reports_module(current_user):
                abort(403, description=REPORTS_MODULE_DENY_MESSAGE)


def register_trusted_host_guard(app):
    configured_hosts = set(app.config.get("TRUSTED_HOSTS", ()))
    if not configured_hosts:
        return
    # Docker's local healthcheck never traverses Cloudflare, so retain only
    # loopback hosts in addition to the operator-provided public domains.
    configured_hosts.update({"127.0.0.1", "localhost", "::1"})

    @app.before_request
    def require_trusted_host():
        host = request.host.split(":", 1)[0].lower()
        if host not in configured_hosts:
            abort(400)


def register_security_headers(app):
    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
        )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response
