from flask import Flask, abort, jsonify, redirect, request, url_for
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import Config
from app.extensions import csrf, db, limiter, login_manager, migrate
from app.security import configuration_errors
from app.ui import register_template_helpers


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.config.setdefault("RATELIMIT_STORAGE_URI", "memory://")
    app.config.setdefault("RATELIMIT_LOGIN_LIMIT", "5 per minute")
    app.config.setdefault("RATELIMIT_EXPORT_LIMIT", "10 per hour")
    for key, value in {
        "STORAGE_PROVIDER": "fake", "STORAGE_BUCKET": "starx-local", "STORAGE_PREFIX": "", "STATIC_ASSET_VERSION": "20260729-8201",
        "STORAGE_UPLOAD_URL_TTL_SECONDS": 300, "STORAGE_DOWNLOAD_URL_TTL_SECONDS": 300,
        "STORAGE_PRESIGNED_POST_MULTIPART_OVERHEAD_BYTES": 1024 * 1024,
        "STORAGE_MAX_IMAGE_SIZE_MB": 50, "STORAGE_MAX_DOCUMENT_SIZE_MB": 200,
        "STORAGE_MAX_VIDEO_SIZE_MB": 500, "STORAGE_MAX_AUDIO_SIZE_MB": 200,
        "STORAGE_MAX_FILES_PER_BATCH": 50, "STORAGE_MAX_BATCH_SIZE_MB": 512,
        "UPLOAD_SELECTION_TTL_SECONDS": 7200, "UPLOAD_SELECTION_MAX_FILES": 500,
        "UPLOAD_SELECTION_MAX_BYTES": 2 * 1024 * 1024 * 1024, "UPLOAD_SINGLE_FILE_MAX_BYTES": 300 * 1024 * 1024,
        "DOWNLOAD_SINGLE_FILE_MAX_BYTES": 300 * 1024 * 1024, "STORAGE_QUOTA_BYTES": 500 * 1024 * 1024 * 1024,
        "DOWNLOAD_MONTHLY_QUOTA_BYTES": 1024 * 1024 * 1024 * 1024,
        "STORAGE_WARN_RATIO": .70, "STORAGE_SOFT_RATIO": .85, "STORAGE_HARD_RATIO": .95,
        "DOWNLOAD_WARN_RATIO": .70, "DOWNLOAD_SOFT_RATIO": .85, "DOWNLOAD_HARD_RATIO": .95,
        "STORAGE_PENDING_UPLOAD_HOURS": 24,
        "DAILY_REPORT_DIRECT_UPLOAD_ENABLED": True, "DAILY_REPORT_MAX_FILES": 30,
        "DAILY_REPORT_MAX_FILES_PER_SECTION": 3,
        "DAILY_REPORT_MAX_FILE_BYTES": 25 * 1024 * 1024, "DAILY_REPORT_MAX_TOTAL_BYTES": 300 * 1024 * 1024,
        "DAILY_REPORT_UPLOAD_CONCURRENCY": 3, "DAILY_REPORT_PRESIGN_TTL_SECONDS": 900,
        "DAILY_REPORT_SESSION_TTL_SECONDS": 86400, "MAX_FORM_PARTS": 1000,
        "STORAGE_CORS_ALLOWED_ORIGINS": ("http://192.168.1.159:5666",),
        "BULK_DOWNLOAD_MAX_FILES": 100, "BULK_DOWNLOAD_MAX_TOTAL_BYTES": 300 * 1024 * 1024,
        "BULK_DOWNLOAD_ZIP_TTL_SECONDS": 86400, "BULK_DOWNLOAD_TEMP_ROOT": "/tmp/starx-bulk-downloads",
        "CELERY_BROKER_URL": None, "CELERY_RESULT_BACKEND": None, "CELERY_TASK_ALWAYS_EAGER": False, "CELERY_TASK_EAGER_PROPAGATES": True, "CELERY_RESULT_EXPIRES_SECONDS": 3600, "CELERY_WORKER_PREFETCH_MULTIPLIER": 1, "CELERY_TASK_ACKS_LATE": True,
        "CELERY_TASK_TIME_LIMIT_IMAGE_SECONDS": 120, "CELERY_TASK_SOFT_TIME_LIMIT_IMAGE_SECONDS": 90, "CELERY_TASK_TIME_LIMIT_VIDEO_SECONDS": 300, "CELERY_TASK_SOFT_TIME_LIMIT_VIDEO_SECONDS": 240, "MEDIA_PROCESSING_MAX_ATTEMPTS": 3,
        "CELERY_TASK_TIME_LIMIT_BULK_DOWNLOAD_SECONDS": 1800, "REPORT_UPLOAD_CLEANUP_INTERVAL_SECONDS": 3600,
        "MEDIA_RECONCILIATION_INTERVAL_SECONDS": 900, "BULK_DOWNLOAD_CLEANUP_INTERVAL_SECONDS": 3600,
        "MEDIA_TEMP_ROOT": "/tmp/starx-media-processing", "MEDIA_IMAGE_THUMBNAIL_MAX_SIZE": 480, "MEDIA_IMAGE_PREVIEW_MAX_SIZE": 1600, "MEDIA_VIDEO_POSTER_MAX_SIZE": 720,
        "MEDIA_CACHE_ENABLED": False,
        "MEDIA_CACHE_ROOT": "/tmp/starx-media-cache" if app.config.get("TESTING") else "/app/cache/media",
        "MEDIA_CACHE_DELIVERY_MODE": "send_file", "MEDIA_CACHE_X_ACCEL_PREFIX": "/_protected_media_cache/",
        "MEDIA_CACHE_MAX_BYTES": 5 * 1024 * 1024 * 1024, "MEDIA_CACHE_MAX_AGE_DAYS": 30,
    }.items():
        app.config.setdefault(key, value)
    if app.config.get("MAX_CONTENT_LENGTH") is None:
        app.config["MAX_CONTENT_LENGTH"] = int(app.config.get("MAX_UPLOAD_MB", 10)) * 1024 * 1024
    startup_errors = configuration_errors(app.config)
    from app.storage.cache import validate_cache_config
    startup_errors.extend(validate_cache_config(app.config))
    if startup_errors:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(startup_errors))
    proxy_hops = int(app.config.get("TRUST_PROXY_HOPS", 0))
    if proxy_hops:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxy_hops, x_proto=proxy_hops, x_host=proxy_hops)

    db.init_app(app)
    migrate.init_app(app, db)
    from app.celery_app import create_celery_app
    create_celery_app(app)
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
    register_upload_error_handlers(app)
    register_template_helpers(app)
    from app.branding import get_current_branding
    from app.account.preferences import normalized_ui_preferences
    from app.navigation import get_active_module, get_sidebar_items, is_project_configuration_endpoint
    @app.context_processor
    def inject_shell_context():
        return {"branding": get_current_branding(), "nav_active_module": get_active_module(),
                "nav_project_configuration": is_project_configuration_endpoint(),
                "sidebar_items": get_sidebar_items(current_user) if current_user.is_authenticated else [],
                "ui_preferences": normalized_ui_preferences(current_user.ui_preferences) if current_user.is_authenticated else normalized_ui_preferences(None)}
    register_cli(app)

    return app


def register_blueprints(app):
    from app.admin import bp as admin_bp
    from app.account import bp as account_bp
    from app.admin_storage import bp as admin_storage_bp
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
    from app.project_documents import bp as project_documents_bp
    from app.company_media import bp as company_media_bp
    from app.customers import bp as customers_bp
    from app.project_operations import bp as project_operations_bp
    from app.reports import bp as reports_bp
    from app.reports.create_v2 import bp as daily_report_create_v2_bp
    from app.users import bp as users_bp

    app.register_blueprint(admin_bp)
    from app.branding import logo as branding_logo
    app.add_url_rule("/branding/logo", endpoint="branding.logo", view_func=branding_logo, methods=["GET"])
    app.register_blueprint(account_bp)
    from app.account.routes import media_display_preview
    app.add_url_rule("/media-display-preview", endpoint="media_display_preview", view_func=media_display_preview, methods=["POST"])
    app.register_blueprint(admin_storage_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(modules_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(dashboard_api_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(project_documents_bp)
    app.register_blueprint(company_media_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(project_operations_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(daily_report_create_v2_bp)
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
        return redirect(url_for("modules.index") if current_user.is_authenticated else url_for("auth.login"))


def register_auth_guard(app):
    public_endpoints = {"auth.login", "health", "healthz", "static"}

    @app.before_request
    def require_login():
        # Let Flask produce a real 404 for removed/unknown routes instead of
        # turning obsolete URLs into login redirects.
        if request.endpoint is None:
            return None
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
        report_endpoints = ("dashboard.", "dashboard_api.", "projects.", "reports.", "issues.", "attachments.", "customers.", "project_operations.")
        is_report_admin = endpoint in {
            "admin.projects_index", "admin.projects_new", "admin.projects_edit",
            "admin.projects_archive", "admin.projects_reporters", "admin.projects_memberships", "admin.categories_index",
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
        from app.security import storage_connect_source
        connect_sources = ["'self'"]
        image_sources = ["'self'", "data:", "blob:"]
        media_sources = ["'self'", "blob:"]
        frame_sources = ["'self'"]
        storage_origin = storage_connect_source(app.config)
        if storage_origin:
            connect_sources.append(storage_origin)
            image_sources.append(storage_origin)
            media_sources.append(storage_origin)
            frame_sources.append(storage_origin)
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com; "
            "worker-src 'self' blob:; "
            "img-src " + " ".join(image_sources) + "; "
            "media-src " + " ".join(media_sources) + "; "
            "frame-src " + " ".join(frame_sources) + "; "
            "connect-src " + " ".join(connect_sources) + "; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
        )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response


def register_upload_error_handlers(app):
    from werkzeug.exceptions import RequestEntityTooLarge
    @app.errorhandler(RequestEntityTooLarge)
    def too_large(_error):
        message = "Yêu cầu quá lớn. Vui lòng dùng trình tải ảnh của hệ thống."
        if request.accept_mimetypes.best == "application/json" or request.path.endswith(("/presign", "/complete")):
            response = jsonify(error=message); response.status_code = 413
        else:
            response = app.make_response((message, 413))
        response.headers["Cache-Control"] = "no-store"
        return response
