from datetime import date, datetime, timezone
from decimal import Decimal
from importlib import metadata
from pathlib import Path

import click
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from flask import current_app
from flask_migrate import upgrade as migrate_upgrade
from sqlalchemy import inspect, text
from werkzeug.security import generate_password_hash

from app.audit import log_audit
from app.admin.services import add_with_sqlite_id
from app.extensions import db
from app.models import (
    Company,
    CompanyDepartment,
    Partner,
    PartnerFieldDefinition,
    PartnerFieldValue,
    PartnerRelationship,
    User,
    UserRole,
    Role,
)
from app.partners.services import _add_with_sqlite_id
from app.security import is_default_secret_key, password_policy_errors, production_configuration_errors


PARTNER_SEED_TABLES = [
    "companies",
    "partners",
    "partner_field_definitions",
    "partner_field_values",
    "partner_relationships",
    "company_departments",
    "partner_field_collections",
    "partner_field_collection_items",
    "partner_department_memberships",
]


def register_cli(app):
    @app.cli.command("sync-permissions")
    @click.option("--apply-defaults", is_flag=True, help="Add missing default grants only.")
    @click.option("--reset-defaults", is_flag=True, help="Replace system role grants with defaults.")
    @click.option("--confirm", default="", help='Required with --reset-defaults: "RESET DEFAULTS".')
    def sync_permissions(apply_defaults, reset_defaults, confirm):
        if reset_defaults and confirm != "RESET DEFAULTS":
            raise click.UsageError('Pass --confirm "RESET DEFAULTS" exactly to reset grants.')
        from app.permissions.sync import sync_registry
        summary = sync_registry(apply_defaults=apply_defaults or reset_defaults, reset_defaults=reset_defaults)
        click.echo("roles={roles_created} permissions={permissions_created} grants={grants_added} deprecated-orphan={deprecated_orphan}".format(**summary))
    @app.cli.command("reset-database")
    @click.option("--confirm", required=True, help='Must be exactly "RESET DATABASE".')
    @click.option("--delete-uploads", is_flag=True, help="Delete files inside UPLOAD_ROOT as well.")
    @click.option("--allow-production", is_flag=True, help="Required when APP_ENV=production.")
    def reset_database(confirm, delete_uploads, allow_production):
        _reset_database(confirm, delete_uploads, allow_production)

    @app.cli.command("seed-admin")
    @click.option("--username", required=True, help="Admin username.")
    @click.option("--password", required=True, help="Admin password.")
    @click.option("--email", required=True, help="Admin email.")
    @click.option("--full-name", required=True, help="Admin full name.")
    def seed_admin(username, password, email, full_name):
        _seed_admin(username, password, email, full_name)

    @app.cli.command("reset-local-dev")
    @click.option("--confirm", required=True, help='Must be exactly "RESET DATABASE".')
    @click.option("--admin-password", required=True, help="Password for the local SUPER_ADMIN.")
    @click.option("--with-demo", is_flag=True, help="Create Partner Management demo data.")
    @click.option("--allow-production", is_flag=True, help="Required when APP_ENV=production.")
    def reset_local_dev(confirm, admin_password, with_demo, allow_production):
        _reset_database(confirm, delete_uploads=False, allow_production=allow_production)
        _seed_admin("admin", admin_password, "admin@example.com", "System Admin")
        if with_demo:
            seed_partner_demo_data()
            click.echo("Đã tạo dữ liệu mẫu Quản lý đối tác.")
        click.echo("Đã hoàn tất reset môi trường local.")

    @app.cli.command("security-audit")
    def security_audit():
        failures = _security_audit()
        if failures:
            raise click.ClickException(f"Security audit failed: {failures} check(s).")

    @app.cli.command("seed-partner-demo")
    def seed_partner_demo():
        summary = seed_partner_demo_data()
        click.echo("Đã tạo dữ liệu mẫu Quản lý đối tác:")
        click.echo(f"- Công ty: {summary['companies_created']} tạo mới, {summary['companies_skipped']} bỏ qua")
        click.echo(f"- Phòng ban: {summary['departments_created']} tạo mới, {summary['departments_skipped']} bỏ qua")
        click.echo(f"- Trường dữ liệu: {summary['fields_created']} tạo mới, {summary['fields_skipped']} bỏ qua")
        click.echo(f"- Đối tác: {summary['partners_created']} tạo mới, {summary['partners_skipped']} bỏ qua")
        click.echo(f"- Dữ liệu mở rộng: {summary['field_values_created']} tạo mới, {summary['field_values_skipped']} bỏ qua")
        click.echo(f"- Quan hệ: {summary['relationships_created']} tạo mới, {summary['relationships_skipped']} bỏ qua")

    @app.cli.group("media-jobs")
    def media_jobs():
        """Inspect and safely retry image/video derivative jobs."""

    @media_jobs.command("status")
    def media_jobs_status_command():
        from app.media_processing.services import media_jobs_status

        summary = media_jobs_status()
        click.echo("Media processing jobs:")
        for status, count in summary["jobs"].items():
            click.echo(f"- {status}: {count}")
        click.echo(f"- ready_storage_objects: {summary['ready_storage_objects']}")

    def _retry_media_jobs(status, dry_run):
        from app.media_processing.services import retry_media_jobs

        summary = retry_media_jobs(status, dry_run=dry_run)
        mode = "dry-run" if dry_run else "apply"
        click.echo(
            "status={status} mode={mode} matched={matched} re_enqueued={re_enqueued} "
            "skipped={skipped} failed_to_enqueue={failed_to_enqueue}".format(
                mode=mode,
                **summary,
            )
        )

    @media_jobs.command("retry-pending")
    @click.option("--dry-run/--apply", default=True, help="Preview changes or enqueue eligible pending jobs.")
    def retry_pending_media_jobs(dry_run):
        _retry_media_jobs("pending", dry_run)

    @media_jobs.command("retry-failed")
    @click.option("--dry-run/--apply", default=True, help="Preview changes or enqueue eligible failed jobs.")
    def retry_failed_media_jobs(dry_run):
        _retry_media_jobs("failed", dry_run)


def _require_reset_confirmation(confirm, allow_production):
    if confirm != "RESET DATABASE":
        raise click.UsageError('Refusing destructive action: pass --confirm "RESET DATABASE" exactly.')
    if current_app.config.get("APP_ENV") == "production" and not allow_production:
        raise click.UsageError("Refusing production reset without --allow-production.")


def _validated_upload_root():
    configured_root = str(current_app.config.get("UPLOAD_ROOT", "")).strip()
    root = Path(configured_root).expanduser().resolve()
    project_root = Path(current_app.root_path).parent.resolve()
    forbidden_roots = {Path(root.anchor), project_root, project_root.parent, Path(current_app.root_path).resolve()}
    if not configured_root or root in forbidden_roots:
        raise click.ClickException("Unsafe UPLOAD_ROOT; refusing to delete uploads.")
    return root


def _delete_upload_contents(root):
    import shutil

    if not root.exists():
        return
    for child in root.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def _reset_database(confirm, delete_uploads, allow_production):
    _require_reset_confirmation(confirm, allow_production)
    click.echo("WARNING: dropping all application database tables and re-running migrations.")
    db.session.remove()
    db.metadata.drop_all(bind=db.engine)
    # This is Alembic's known version table. Do not drop unrelated database tables.
    if inspect(db.engine).has_table("alembic_version"):
        with db.engine.begin() as connection:
            connection.execute(text("DROP TABLE alembic_version"))
    migrate_upgrade(directory=str(Path(current_app.root_path).parent / "migrations"))
    if delete_uploads:
        upload_root = _validated_upload_root()
        _delete_upload_contents(upload_root)
        click.echo(f"Deleted upload contents: {upload_root}")
    click.echo("Database reset and migrated to current head.")


def _seed_admin(username, password, email, full_name):
    errors = password_policy_errors(password)
    if errors:
        raise click.UsageError(" ".join(errors))
    username = username.strip()
    email = email.strip()
    full_name = full_name.strip()
    if not username or not email or not full_name:
        raise click.UsageError("username, email and full-name must not be empty.")

    # Synchronize before adding a User: sync_registry commits, and the legacy
    # users.role column is still NOT NULL in this compatibility release.
    role = Role.query.filter_by(code=UserRole.SUPER_ADMIN.value).first()
    if role is None:
        from app.permissions.sync import sync_registry
        sync_registry()
        role = Role.query.filter_by(code=UserRole.SUPER_ADMIN.value).one()

    user = User.query.filter_by(username=username).first()
    email_user = User.query.filter_by(email=email).first()
    if user and email_user and user.id != email_user.id:
        raise click.UsageError("Username and email belong to different existing accounts.")
    user = user or email_user
    action = "user.seed_admin.update" if user else "user.seed_admin"
    if user is None:
        user = User(username=username, email=email, full_name=full_name, password_hash="")
        add_with_sqlite_id(user)
    user.username = username
    user.email = email
    user.full_name = full_name
    user.password_hash = generate_password_hash(password)
    user.role = role
    user.role_id = role.id
    user.legacy_role = UserRole.SUPER_ADMIN.value
    user.is_active = True
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if user.created_at is None:
        user.created_at = now
    user.updated_at = now
    db.session.flush()
    audit_record = log_audit(action, "User", user.id, new_values={"username": user.username, "email": user.email, "role": user.role_code})
    audit_record.created_at = now
    db.session.commit()
    click.echo(f"SUPER_ADMIN seeded: username={username}")


def _audit_line(status, name, detail):
    click.echo(f"{status:<4} {name}: {detail}")


def _migration_head():
    alembic_config = AlembicConfig(str(Path(current_app.root_path).parent / "migrations" / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(Path(current_app.root_path).parent / "migrations"))
    return ScriptDirectory.from_config(alembic_config).get_current_head()


def _security_audit():
    failures = 0

    def check(condition, name, success, failure, warn=False):
        nonlocal failures
        if condition:
            _audit_line("WARN" if warn else "PASS", name, success)
        else:
            _audit_line("FAIL", name, failure)
            failures += 1

    config = current_app.config
    production_errors = production_configuration_errors(config)
    check(not production_errors, "production-guards", "production configuration is safe", "; ".join(production_errors) or "unsafe configuration")
    weak_secret = is_default_secret_key(config.get("SECRET_KEY"))
    if config.get("APP_ENV") == "production":
        check(not weak_secret, "secret-key", "strong non-default key configured", "missing/default/short SECRET_KEY")
    else:
        _audit_line("WARN" if weak_secret else "PASS", "secret-key", "weak local default" if weak_secret else "non-default key configured")
    check(config.get("SESSION_COOKIE_HTTPONLY") and str(config.get("SESSION_COOKIE_SAMESITE", "")).lower() in {"lax", "strict"}, "session-cookies", "HttpOnly and SameSite configured", "insecure session cookie settings")
    if config.get("APP_ENV") == "production":
        check(config.get("SESSION_COOKIE_SECURE"), "secure-cookie", "Secure cookie enabled", "SESSION_COOKIE_SECURE is disabled")
    else:
        _audit_line("WARN" if not config.get("SESSION_COOKIE_SECURE") else "PASS", "secure-cookie", "disabled outside production" if not config.get("SESSION_COOKIE_SECURE") else "enabled")
    check("csrf" in current_app.extensions, "csrf", "CSRF protection initialized", "CSRF protection missing")
    with current_app.test_request_context("/security-audit"):
        response = current_app.make_response("")
        response = current_app.process_response(response)
    check("frame-ancestors 'none'" in response.headers.get("Content-Security-Policy", "") and response.headers.get("X-Frame-Options") == "DENY", "security-headers", "CSP and frame protection enabled", "security headers missing")
    storage_uri = config.get("RATELIMIT_STORAGE_URI", "")
    check(bool(storage_uri), "rate-limit", "rate-limit storage configured", "RATELIMIT_STORAGE_URI missing")
    if storage_uri == "memory://":
        _audit_line(
            "WARN",
            "rate-limit-storage",
            "memory:// is per worker and resets when the application restarts",
        )
    else:
        _audit_line("PASS", "rate-limit-storage", storage_uri)
    storage_provider = str(config.get("STORAGE_PROVIDER", "disabled")).lower()
    check(storage_provider in {"fake", "s3", "disabled"}, "storage-provider-config", "recognized storage provider", "unknown STORAGE_PROVIDER")
    check(config.get("APP_ENV") != "production" or storage_provider != "fake", "storage-fake-provider-not-production", "fake provider is not used in production", "STORAGE_PROVIDER=fake in production")
    upload_limits = ("STORAGE_MAX_IMAGE_SIZE_MB", "STORAGE_MAX_DOCUMENT_SIZE_MB", "STORAGE_MAX_VIDEO_SIZE_MB", "STORAGE_MAX_AUDIO_SIZE_MB", "STORAGE_MAX_FILES_PER_BATCH", "STORAGE_MAX_BATCH_SIZE_MB")
    check(all(int(config.get(name, 0)) > 0 for name in upload_limits), "storage-upload-limits-configured", "storage upload limits configured", "one or more storage limits are invalid")
    check(bool(config.get("CELERY_BROKER_URL")) and bool(config.get("CELERY_RESULT_BACKEND")), "celery-config-present", "Celery broker/result configured", "Celery broker/result missing")
    check(config.get("APP_ENV") != "production" or not config.get("CELERY_TASK_ALWAYS_EAGER"), "celery-eager-not-production", "Celery eager disabled in production", "CELERY_TASK_ALWAYS_EAGER enabled in production")
    check(bool(config.get("MEDIA_TEMP_ROOT")), "media-temp-root-configured", "media temp root configured", "MEDIA_TEMP_ROOT missing")
    check(all(int(config.get(n, 0)) > 0 for n in ("CELERY_TASK_TIME_LIMIT_IMAGE_SECONDS", "CELERY_TASK_TIME_LIMIT_VIDEO_SECONDS")), "media-timeouts-configured", "media timeouts configured", "media timeout missing")
    check(all(int(config.get(n, 0)) > 0 for n in ("BULK_DOWNLOAD_MAX_FILES", "BULK_DOWNLOAD_MAX_TOTAL_BYTES", "BULK_DOWNLOAD_ZIP_TTL_SECONDS", "CELERY_TASK_TIME_LIMIT_BULK_DOWNLOAD_SECONDS")), "bulk-download-configured", "bulk ZIP limits configured", "bulk ZIP configuration missing")
    check(bool(config.get("BULK_DOWNLOAD_TEMP_ROOT")), "bulk-download-temp-root", "bulk ZIP temp root configured", "bulk ZIP temp root missing")
    check(all(int(config.get(n, 0)) > 0 for n in ("MEDIA_IMAGE_THUMBNAIL_MAX_SIZE", "MEDIA_IMAGE_PREVIEW_MAX_SIZE", "MEDIA_VIDEO_POSTER_MAX_SIZE", "MEDIA_PROCESSING_MAX_ATTEMPTS")), "media-processing-limits-configured", "media processing limits configured", "media processing limit missing")
    try:
        _validated_upload_root()
        upload_root_safe = True
    except click.ClickException:
        upload_root_safe = False
    check(upload_root_safe, "upload-controls", "bounded upload root configured", "unsafe UPLOAD_ROOT")
    _audit_line("PASS", "export-safety", "no export feature is implemented")
    try:
        requirements = (Path(current_app.root_path).parent / "requirements.txt").read_text().splitlines()
        pinned_requirements = [item.strip() for item in requirements if item.strip() and not item.startswith("#")]
        check(all("==" in item for item in pinned_requirements), "dependencies-pinned", "dependencies are pinned", "one or more dependencies are unpinned")
        unavailable = []
        for requirement in pinned_requirements:
            package, expected_version = requirement.split("==", 1)
            package = package.split("[", 1)[0]
            try:
                if metadata.version(package) != expected_version:
                    unavailable.append(package)
            except metadata.PackageNotFoundError:
                unavailable.append(package)
        check(not unavailable, "dependencies-installed", "all pinned dependencies are installed", "missing/version mismatch: " + ", ".join(unavailable))
        inspector = inspect(db.engine)
        rbac_tables = {"roles", "permissions", "role_permissions"}
        check(rbac_tables.issubset(set(inspector.get_table_names())), "rbac-schema", "RBAC tables exist", "one or more RBAC tables are missing")
        invalid_role_users = User.query.outerjoin(Role).filter((User.role_id.is_(None)) | (Role.id.is_(None))).count()
        check(invalid_role_users == 0, "rbac-user-roles", "all users reference a valid role", f"{invalid_role_users} user(s) have an invalid role_id")
        version = db.session.execute(text("SELECT version_num FROM alembic_version")).scalar()
        check(version == _migration_head(), "migration-state", f"at head {version}", f"current={version}, expected={_migration_head()}")
        hashes = [row[0] for row in db.session.query(User.password_hash).all()]
        check(all(value.startswith(("scrypt:", "pbkdf2:")) for value in hashes), "password-hashes", "Werkzeug password hashes in use", "weak or invalid password hash found")
        check(User.query.join(Role).filter(User.role_id == Role.id, Role.code == UserRole.SUPER_ADMIN.value, User.is_active.is_(True)).count() > 0, "super-admin", "active SUPER_ADMIN exists", "no active SUPER_ADMIN")
        demos = Partner.query.filter(Partner.notes.like(f"{DEMO_NOTE_PREFIX}%")).count()
        if config.get("APP_ENV") == "production":
            check(demos == 0, "production-demo-data", "no demo partners", f"{demos} demo partner(s) found")
        else:
            _audit_line("PASS", "production-demo-data", "not a production environment")
    except Exception as exc:
        _audit_line("FAIL", "database-checks", type(exc).__name__)
        failures += 1
        db.session.rollback()
    return failures


def sync_postgres_sequence(table_name, column_name="id"):
    if db.engine.name != "postgresql":
        return
    if not inspect(db.engine).has_table(table_name):
        return
    sequence_name = db.session.execute(
        text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
        {"table_name": table_name, "column_name": column_name},
    ).scalar()
    if not sequence_name:
        return
    sql = text(
        f"""
        SELECT setval(
            :sequence_name,
            COALESCE((SELECT MAX({column_name}) FROM {table_name}), 1),
            (SELECT COUNT(*) > 0 FROM {table_name})
        )
        """
    )
    db.session.execute(sql, {"sequence_name": sequence_name})


def sync_partner_demo_sequences():
    for table_name in PARTNER_SEED_TABLES:
        sync_postgres_sequence(table_name)


def _seed_add(instance):
    if db.engine.name == "sqlite":
        _add_with_sqlite_id(instance)
    else:
        db.session.add(instance)


DEMO_NOTE_PREFIX = "[DEMO] "


COMPANY_DEMOS = [
    {
        "name": "Công ty Xây dựng An Bình",
        "industry": "Xây dựng",
        "address": "Hà Nội",
        "website": "https://anbinh.example.com",
        "phone": "0240000001",
        "email": "contact@anbinh.example.com",
    },
    {
        "name": "Công ty Cơ điện Minh Phát",
        "industry": "MEP / Cơ điện",
        "address": "TP.HCM",
        "website": "https://minhphat.example.com",
        "phone": "0280000002",
        "email": "contact@minhphat.example.com",
    },
    {
        "name": "Công ty Vật liệu Hòa Sơn",
        "industry": "Vật liệu xây dựng",
        "address": "Đà Nẵng",
        "website": "https://hoason.example.com",
        "phone": "0236000003",
        "email": "contact@hoason.example.com",
    },
    {
        "name": "Công ty Tư vấn Thiết kế Nova",
        "industry": "Tư vấn thiết kế",
        "address": "Hà Nội",
        "website": "https://nova.example.com",
        "phone": "0240000004",
        "email": "contact@nova.example.com",
    },
    {
        "name": "Ban Quản lý Dự án StarX",
        "industry": "Chủ đầu tư / BQLDA",
        "address": "Hà Nội",
        "website": "https://starx.example.com",
        "phone": "0240000005",
        "email": "pmu@starx.example.com",
    },
]


FIELD_DEMOS = [
    {"label": "Sở thích", "field_key": "hobby", "field_type": "text", "group_name": "Cá nhân", "options_json": []},
    {
        "label": "Phong cách làm việc",
        "field_key": "working_style",
        "field_type": "select",
        "group_name": "Tính cách / Phong cách",
        "options_json": ["Thân thiện", "Quyết đoán", "Kỹ thuật", "Tài chính", "Khó tiếp cận"],
    },
    {"label": "Mức độ thân thiết", "field_key": "relationship_level", "field_type": "number", "group_name": "Quan hệ", "options_json": []},
    {
        "label": "Lĩnh vực quan tâm",
        "field_key": "interests",
        "field_type": "multi_select",
        "group_name": "Quan hệ",
        "options_json": ["Tiến độ", "Chất lượng", "Chi phí", "Pháp lý", "An toàn", "Nhân sự"],
    },
    {"label": "Ngày sinh nhật", "field_key": "birthday_note", "field_type": "date", "group_name": "Cá nhân", "options_json": []},
    {
        "label": "Kênh liên hệ ưu tiên",
        "field_key": "preferred_contact_channel",
        "field_type": "select",
        "group_name": "Liên hệ",
        "options_json": ["Điện thoại", "Zalo", "Email", "Gặp trực tiếp"],
    },
    {"label": "Ghi chú khi làm việc", "field_key": "working_note", "field_type": "textarea", "group_name": "Ghi chú", "options_json": []},
    {"label": "Người giới thiệu", "field_key": "referred_by", "field_type": "text", "group_name": "Quan hệ", "options_json": []},
]


PARTNER_DEMOS = [
    {
        "full_name": "Nguyễn Văn Minh",
        "company": "Công ty Xây dựng An Bình",
        "department": "Ban điều hành",
        "position": "Tổng giám đốc",
        "phone": "0901000001",
        "email": "minh.nguyen@anbinh.example.com",
        "address": "Hà Nội",
        "birth_date": "1978-03-12",
        "notes": "Đầu mối quyết định các vấn đề tiến độ và ngân sách.",
        "dynamic": {
            "hobby": "Golf, cà phê sáng",
            "working_style": "Quyết đoán",
            "relationship_level": 4,
            "interests": ["Tiến độ", "Chi phí"],
            "preferred_contact_channel": "Gặp trực tiếp",
            "working_note": "Nên chuẩn bị số liệu ngắn gọn trước khi gặp.",
            "referred_by": "Hội doanh nghiệp xây dựng Hà Nội",
        },
    },
    {
        "full_name": "Trần Thị Lan",
        "company": "Công ty Xây dựng An Bình",
        "department": "Phòng mua hàng",
        "position": "Trưởng phòng mua hàng",
        "phone": "0901000002",
        "email": "lan.tran@anbinh.example.com",
        "address": "Hà Nội",
        "birth_date": "1984-08-24",
        "notes": "Theo sát báo giá và điều khoản thanh toán.",
        "dynamic": {
            "hobby": "Du lịch",
            "working_style": "Tài chính",
            "relationship_level": 3,
            "interests": ["Chi phí", "Chất lượng"],
            "preferred_contact_channel": "Zalo",
            "working_note": "Cần gửi bảng so sánh chi phí rõ ràng.",
        },
    },
    {
        "full_name": "Phạm Quốc Huy",
        "company": "Công ty Xây dựng An Bình",
        "department": "Ban chỉ huy công trường",
        "position": "Chỉ huy trưởng",
        "phone": "0901000003",
        "email": "huy.pham@anbinh.example.com",
        "address": "Hà Nội",
        "birth_date": "1982-11-02",
        "notes": "Ưu tiên trao đổi trực tiếp tại công trường.",
        "dynamic": {
            "hobby": "Bóng đá",
            "working_style": "Thân thiện",
            "relationship_level": 4,
            "interests": ["Tiến độ", "An toàn"],
            "preferred_contact_channel": "Điện thoại",
        },
    },
    {
        "full_name": "Lê Hoàng Anh",
        "company": "Công ty Cơ điện Minh Phát",
        "department": "Kỹ thuật",
        "position": "Trưởng phòng",
        "is_department_head": True,
        "phone": "0902000001",
        "email": "anh.le@minhphat.example.com",
        "address": "TP.HCM",
        "birth_date": "1980-06-18",
        "notes": "Quan tâm nhiều tới hồ sơ kỹ thuật và nghiệm thu.",
        "dynamic": {
            "hobby": "Công nghệ, xe hơi",
            "working_style": "Kỹ thuật",
            "relationship_level": 5,
            "interests": ["Chất lượng", "An toàn"],
            "preferred_contact_channel": "Điện thoại",
            "working_note": "Gửi bản vẽ và checklist kỹ thuật trước cuộc họp.",
        },
    },
    {
        "full_name": "Võ Minh Phát",
        "company": "Công ty Cơ điện Minh Phát",
        "department": "Ban giám đốc",
        "position": "Giám đốc",
        "phone": "0902000002",
        "email": "phat.vo@minhphat.example.com",
        "address": "TP.HCM",
        "birth_date": "1976-01-20",
        "notes": "Người quyết định hợp đồng MEP.",
        "dynamic": {
            "hobby": "Tennis",
            "working_style": "Quyết đoán",
            "relationship_level": 3,
            "interests": ["Chi phí", "Tiến độ"],
            "preferred_contact_channel": "Email",
        },
    },
    {
        "full_name": "Đặng Thị Thu Hà",
        "company": "Công ty Cơ điện Minh Phát",
        "department": "QA/QC",
        "position": "Trưởng phòng",
        "is_department_head": True,
        "phone": "0902000003",
        "email": "ha.dang@minhphat.example.com",
        "address": "TP.HCM",
        "birth_date": "1988-09-09",
        "notes": "Cần hồ sơ nghiệm thu đầy đủ.",
        "dynamic": {
            "hobby": "Đọc sách",
            "working_style": "Kỹ thuật",
            "relationship_level": 4,
            "interests": ["Chất lượng", "Pháp lý"],
            "preferred_contact_channel": "Zalo",
        },
    },
    {
        "full_name": "Hoàng Văn Sơn",
        "company": "Công ty Vật liệu Hòa Sơn",
        "department": "Ban giám đốc",
        "position": "Giám đốc",
        "phone": "0903000001",
        "email": "son.hoang@hoason.example.com",
        "address": "Đà Nẵng",
        "birth_date": "1975-12-01",
        "notes": "Đầu mối chốt năng lực cung ứng vật liệu.",
        "dynamic": {
            "hobby": "Câu cá",
            "working_style": "Thân thiện",
            "relationship_level": 4,
            "interests": ["Tiến độ", "Chi phí"],
            "preferred_contact_channel": "Điện thoại",
        },
    },
    {
        "full_name": "Ngô Thị Mai",
        "company": "Công ty Vật liệu Hòa Sơn",
        "department": "Kinh doanh",
        "position": "Trưởng phòng",
        "is_department_head": True,
        "phone": "0903000002",
        "email": "mai.ngo@hoason.example.com",
        "address": "Đà Nẵng",
        "birth_date": "1986-04-15",
        "notes": "Phản hồi nhanh về báo giá và lịch giao hàng.",
        "dynamic": {
            "hobby": "Ẩm thực",
            "working_style": "Tài chính",
            "relationship_level": 3,
            "interests": ["Chi phí", "Chất lượng"],
            "preferred_contact_channel": "Email",
        },
    },
    {
        "full_name": "Bùi Thanh Tùng",
        "company": "Công ty Vật liệu Hòa Sơn",
        "department": "Kho vận",
        "position": "Điều phối kho vận",
        "phone": "0903000003",
        "email": "tung.bui@hoason.example.com",
        "address": "Đà Nẵng",
        "birth_date": "1990-07-21",
        "notes": "Theo dõi xe và lịch giao vật tư.",
        "dynamic": {
            "hobby": "Chạy bộ",
            "working_style": "Kỹ thuật",
            "relationship_level": 3,
            "interests": ["Tiến độ", "An toàn"],
            "preferred_contact_channel": "Zalo",
        },
    },
    {
        "full_name": "Đỗ Minh Quân",
        "company": "Công ty Tư vấn Thiết kế Nova",
        "department": "Ban giám đốc",
        "position": "Giám đốc thiết kế",
        "phone": "0904000001",
        "email": "quan.do@nova.example.com",
        "address": "Hà Nội",
        "birth_date": "1979-05-05",
        "notes": "Ưu tiên trao đổi phương án thiết kế tổng thể.",
        "dynamic": {
            "hobby": "Nhiếp ảnh kiến trúc",
            "working_style": "Kỹ thuật",
            "relationship_level": 4,
            "interests": ["Chất lượng", "Pháp lý"],
            "preferred_contact_channel": "Gặp trực tiếp",
        },
    },
    {
        "full_name": "Lý Thu Trang",
        "company": "Công ty Tư vấn Thiết kế Nova",
        "department": "Kiến trúc",
        "position": "Trưởng phòng",
        "is_department_head": True,
        "phone": "0904000002",
        "email": "trang.ly@nova.example.com",
        "address": "Hà Nội",
        "birth_date": "1987-10-30",
        "notes": "Cần thống nhất đầu bài rõ trước khi triển khai.",
        "dynamic": {
            "hobby": "Triển lãm nghệ thuật",
            "working_style": "Thân thiện",
            "relationship_level": 4,
            "interests": ["Chất lượng", "Tiến độ"],
            "preferred_contact_channel": "Email",
        },
    },
    {
        "full_name": "Phan Đức Long",
        "company": "Công ty Tư vấn Thiết kế Nova",
        "department": "Kết cấu",
        "position": "Trưởng phòng",
        "is_department_head": True,
        "phone": "0904000003",
        "email": "long.phan@nova.example.com",
        "address": "Hà Nội",
        "birth_date": "1985-02-11",
        "notes": "Quan tâm tiêu chuẩn kỹ thuật và hồ sơ tính toán.",
        "dynamic": {
            "hobby": "Cờ tướng",
            "working_style": "Kỹ thuật",
            "relationship_level": 3,
            "interests": ["Chất lượng", "An toàn"],
            "preferred_contact_channel": "Điện thoại",
        },
    },
    {
        "full_name": "Vũ Hải Nam",
        "company": "Ban Quản lý Dự án StarX",
        "department": "Ban lãnh đạo",
        "position": "Giám đốc dự án",
        "phone": "0905000001",
        "email": "nam.vu@starx.example.com",
        "address": "Hà Nội",
        "birth_date": "1977-09-17",
        "notes": "Theo dõi tổng tiến độ và rủi ro dự án.",
        "dynamic": {
            "hobby": "Đạp xe",
            "working_style": "Quyết đoán",
            "relationship_level": 5,
            "interests": ["Tiến độ", "Chi phí", "Pháp lý"],
            "preferred_contact_channel": "Gặp trực tiếp",
        },
    },
    {
        "full_name": "Trần Thị Bích",
        "company": "Ban Quản lý Dự án StarX",
        "department": "Ban lãnh đạo",
        "position": "CFO",
        "phone": "0905000004",
        "email": "bich.tran@starx.example.com",
        "address": "Hà Nội",
        "birth_date": "1980-12-04",
        "notes": "Theo dõi ngân sách và dòng tiền dự án.",
        "dynamic": {
            "hobby": "Đọc sách quản trị",
            "working_style": "Tài chính",
            "relationship_level": 4,
            "interests": ["Chi phí", "Pháp lý"],
            "preferred_contact_channel": "Email",
        },
    },
    {
        "full_name": "Lê Quốc Cường",
        "company": "Ban Quản lý Dự án StarX",
        "department": "Ban lãnh đạo",
        "position": "COO",
        "phone": "0905000005",
        "email": "cuong.le@starx.example.com",
        "address": "Hà Nội",
        "birth_date": "1979-07-13",
        "notes": "Điều phối vận hành giữa các bộ phận dự án.",
        "dynamic": {
            "hobby": "Chạy bộ",
            "working_style": "Quyết đoán",
            "relationship_level": 4,
            "interests": ["Tiến độ", "Nhân sự"],
            "preferred_contact_channel": "Gặp trực tiếp",
        },
    },
    {
        "full_name": "Nguyễn Thị Hạnh",
        "company": "Ban Quản lý Dự án StarX",
        "department": "Quản lý hợp đồng",
        "position": "Trưởng phòng",
        "is_department_head": True,
        "phone": "0905000002",
        "email": "hanh.nguyen@starx.example.com",
        "address": "Hà Nội",
        "birth_date": "1983-03-28",
        "notes": "Rà soát kỹ điều khoản hợp đồng và phụ lục.",
        "dynamic": {
            "hobby": "Yoga",
            "working_style": "Tài chính",
            "relationship_level": 4,
            "interests": ["Pháp lý", "Chi phí"],
            "preferred_contact_channel": "Email",
        },
    },
    {
        "full_name": "Tạ Quang Dũng",
        "company": "Ban Quản lý Dự án StarX",
        "department": "Hiện trường",
        "position": "Trưởng phòng",
        "is_department_head": True,
        "phone": "0905000003",
        "email": "dung.ta@starx.example.com",
        "address": "Hà Nội",
        "birth_date": "1981-11-19",
        "notes": "Cần cập nhật nhanh các vấn đề hiện trường.",
        "dynamic": {
            "hobby": "Leo núi",
            "working_style": "Khó tiếp cận",
            "relationship_level": 2,
            "interests": ["An toàn", "Tiến độ", "Nhân sự"],
            "preferred_contact_channel": "Điện thoại",
            "working_note": "Nên gọi trước, sau đó gửi tóm tắt qua Zalo.",
        },
    },
]


RELATIONSHIP_DEMOS = [
    ("Nguyễn Văn Minh", "Trần Thị Lan"),
    ("Nguyễn Văn Minh", "Phạm Quốc Huy"),
    ("Võ Minh Phát", "Lê Hoàng Anh"),
    ("Võ Minh Phát", "Đặng Thị Thu Hà"),
    ("Hoàng Văn Sơn", "Ngô Thị Mai"),
    ("Hoàng Văn Sơn", "Bùi Thanh Tùng"),
    ("Đỗ Minh Quân", "Lý Thu Trang"),
    ("Đỗ Minh Quân", "Phan Đức Long"),
    ("Vũ Hải Nam", "Nguyễn Thị Hạnh"),
    ("Vũ Hải Nam", "Tạ Quang Dũng"),
]


DEPARTMENT_DEMOS = {
    "Ban Quản lý Dự án StarX": [
        ("Hội đồng quản trị", None, True),
        ("Ban lãnh đạo", "Hội đồng quản trị", True),
        ("Ban giám đốc", "Ban lãnh đạo", False),
        ("Ban điều hành dự án", "Ban giám đốc", False),
        ("Hiện trường", "Ban điều hành dự án", False),
        ("Kỹ thuật", "Ban điều hành dự án", False),
        ("Quản lý hợp đồng", "Ban giám đốc", False),
        ("Kế toán", "Ban giám đốc", False),
    ],
    "Công ty Cơ điện Minh Phát": [
        ("Ban giám đốc", None, False),
        ("Kỹ thuật", "Ban giám đốc", False),
        ("QA/QC", "Kỹ thuật", False),
        ("Thi công", "Kỹ thuật", False),
    ],
    "Công ty Tư vấn Thiết kế Nova": [
        ("Ban giám đốc", None, False),
        ("Kiến trúc", "Ban giám đốc", False),
        ("Kết cấu", "Ban giám đốc", False),
        ("QS", "Ban giám đốc", False),
    ],
    "Công ty Xây dựng An Bình": [
        ("Ban điều hành", None, False),
        ("Phòng mua hàng", "Ban điều hành", False),
        ("Ban chỉ huy công trường", "Ban điều hành", False),
    ],
    "Công ty Vật liệu Hòa Sơn": [
        ("Ban giám đốc", None, False),
        ("Kinh doanh", "Ban giám đốc", False),
        ("Kho vận", "Ban giám đốc", False),
    ],
}


DEPARTMENT_ALIASES = {}


def seed_partner_demo_data():
    summary = {
        "companies_created": 0,
        "companies_skipped": 0,
        "fields_created": 0,
        "fields_skipped": 0,
        "departments_created": 0,
        "departments_skipped": 0,
        "partners_created": 0,
        "partners_skipped": 0,
        "field_values_created": 0,
        "field_values_skipped": 0,
        "relationships_created": 0,
        "relationships_skipped": 0,
    }

    try:
        sync_partner_demo_sequences()

        companies = {}
        for item in COMPANY_DEMOS:
            company = Company.query.filter(Company.name == item["name"]).first()
            if company:
                summary["companies_skipped"] += 1
            else:
                company = Company(notes=f"{DEMO_NOTE_PREFIX}Dữ liệu mẫu Quản lý đối tác.")
                _seed_add(company)
                summary["companies_created"] += 1
            company.name = item["name"]
            company.industry = item["industry"]
            company.address = item["address"]
            company.website = item["website"]
            company.phone = item["phone"]
            company.email = item["email"]
            company.is_active = True
            company.deleted_at = None
            if company.id is None:
                db.session.flush()
            companies[company.name] = company

        fields = {}
        for sort_order, item in enumerate(FIELD_DEMOS, start=1):
            field = PartnerFieldDefinition.query.filter(PartnerFieldDefinition.field_key == item["field_key"]).first()
            if field:
                summary["fields_skipped"] += 1
            else:
                field = PartnerFieldDefinition(field_key=item["field_key"])
                _seed_add(field)
                summary["fields_created"] += 1
            field.label = item["label"]
            field.field_type = item["field_type"]
            field.group_name = item["group_name"]
            field.options_json = item["options_json"]
            field.sort_order = sort_order
            field.is_required = False
            field.is_active = True
            fields[field.field_key] = field

        db.session.flush()

        departments = {}
        for company_name, rows in DEPARTMENT_DEMOS.items():
            company = companies[company_name]
            departments.setdefault(company_name, {})
            for sort_order, row in enumerate(rows, start=1):
                name, _parent_name, is_special = _department_demo_row(row)
                department = CompanyDepartment.query.filter_by(company_id=company.id, name=name).first()
                if department:
                    summary["departments_skipped"] += 1
                else:
                    department = CompanyDepartment(company_id=company.id, name=name)
                    _seed_add(department)
                    db.session.flush()
                    summary["departments_created"] += 1
                department.display_order = sort_order
                department.is_active = True
                department.is_special_department = is_special
                departments[company_name][name] = department
            db.session.flush()
            for row in rows:
                name, parent_name, _is_special = _department_demo_row(row)
                department = departments[company_name][name]
                department.parent_department_id = departments[company_name][parent_name].id if parent_name else None

        partners = {}
        for item in PARTNER_DEMOS:
            partner = Partner.query.filter(Partner.email == item["email"]).first()
            if partner:
                summary["partners_skipped"] += 1
            else:
                partner = Partner(email=item["email"])
                _seed_add(partner)
                summary["partners_created"] += 1
            partner.full_name = item["full_name"]
            partner.company = companies[item["company"]]
            department_name = DEPARTMENT_ALIASES.get(item["department"], item["department"])
            department = departments[item["company"]].get(department_name)
            partner.department_id = department.id if department else None
            partner.department = department.name if department else item["department"]
            partner.position = item["position"]
            partner.is_department_head = bool(item.get("is_department_head")) and bool(department) and not department.is_special_department
            partner.phone = item["phone"]
            partner.address = item["address"]
            partner.birth_date = date.fromisoformat(item["birth_date"])
            partner.notes = f"{DEMO_NOTE_PREFIX}{item['notes']}"
            partner.is_active = True
            partner.deleted_at = None
            db.session.flush()
            if partner.id is None:
                raise RuntimeError("Partner ID was not generated before creating field values.")
            partners[partner.full_name] = partner
            _sync_demo_field_values(partner, fields, item["dynamic"], summary)

        db.session.flush()

        for manager_name, subordinate_name in RELATIONSHIP_DEMOS:
            manager = partners[manager_name]
            subordinate = partners[subordinate_name]
            existing = PartnerRelationship.query.filter(
                PartnerRelationship.company_id == subordinate.company_id,
                PartnerRelationship.partner_id == subordinate.id,
                PartnerRelationship.parent_partner_id == manager.id,
                PartnerRelationship.relationship_type == "manager",
            ).first()
            if existing:
                summary["relationships_skipped"] += 1
                existing.is_active = True
                existing.deleted_at = None
                existing.department_id = subordinate.department_id
                existing.department = subordinate.company_department.name if subordinate.company_department else subordinate.department
                existing.position_title = subordinate.position
                existing.is_department_head = False
            else:
                existing = PartnerRelationship(
                    company_id=subordinate.company_id,
                    department_id=subordinate.department_id,
                    partner_id=subordinate.id,
                    from_partner_id=manager.id,
                    to_partner_id=subordinate.id,
                    department=subordinate.company_department.name if subordinate.company_department else subordinate.department,
                    position_title=subordinate.position,
                    parent_partner_id=manager.id,
                    relationship_type="manager",
                    is_department_head=False,
                    display_order=0,
                    note=f"{DEMO_NOTE_PREFIX}Quan hệ cấp trên - cấp dưới.",
                    notes=f"{DEMO_NOTE_PREFIX}Quan hệ cấp trên - cấp dưới.",
                )
                _seed_add(existing)
                summary["relationships_created"] += 1

        subordinates = {subordinate_name for _manager_name, subordinate_name in RELATIONSHIP_DEMOS}
        for partner_name, partner in partners.items():
            if partner_name in subordinates:
                continue
            relationship_type = "none" if partner.company_department and partner.company_department.is_special_department else "direct_report"
            existing = PartnerRelationship.query.filter(
                PartnerRelationship.company_id == partner.company_id,
                PartnerRelationship.partner_id == partner.id,
                PartnerRelationship.parent_partner_id.is_(None),
                PartnerRelationship.relationship_type.in_([relationship_type, "direct_report"] if relationship_type == "none" else [relationship_type]),
            ).first()
            if existing:
                summary["relationships_skipped"] += 1
                existing.relationship_type = relationship_type
                existing.from_partner_id = partner.id
                existing.to_partner_id = partner.id
                existing.department_id = partner.department_id
                existing.department = partner.company_department.name if partner.company_department else partner.department
                existing.position_title = partner.position
                existing.parent_partner_id = None
                existing.is_department_head = False
                existing.is_active = True
                existing.deleted_at = None
            else:
                existing = PartnerRelationship(
                    company_id=partner.company_id,
                    department_id=partner.department_id,
                    partner_id=partner.id,
                    from_partner_id=partner.id,
                    to_partner_id=partner.id,
                    department=partner.company_department.name if partner.company_department else partner.department,
                    position_title=partner.position,
                    parent_partner_id=None,
                    relationship_type=relationship_type,
                    is_department_head=False,
                    display_order=0,
                    note=f"{DEMO_NOTE_PREFIX}Vai trò trong sơ đồ tổ chức.",
                    notes=f"{DEMO_NOTE_PREFIX}Vai trò trong sơ đồ tổ chức.",
                )
                _seed_add(existing)
                summary["relationships_created"] += 1

        db.session.commit()
        return summary
    except Exception:
        db.session.rollback()
        raise


def _sync_demo_field_values(partner, fields, dynamic_values, summary):
    for sort_order, field_key in enumerate([item["field_key"] for item in FIELD_DEMOS], start=1):
        if field_key not in dynamic_values:
            continue
        field = fields[field_key]
        field_value = (
            PartnerFieldValue.query.filter(
                PartnerFieldValue.partner_id == partner.id,
                PartnerFieldValue.field_definition_id == field.id,
                PartnerFieldValue.field_key_snapshot == field.field_key,
            )
            .first()
        )
        if field_value:
            summary["field_values_skipped"] += 1
        else:
            field_value = PartnerFieldValue(partner_id=partner.id)
            _seed_add(field_value)
            summary["field_values_created"] += 1
        field_value.field_definition_id = field.id
        field_value.field_label_snapshot = field.label
        field_value.field_key_snapshot = field.field_key
        field_value.field_type_snapshot = field.field_type
        field_value.group_name_snapshot = field.group_name
        field_value.sort_order = sort_order
        _set_partner_field_value(field_value, field.field_type, dynamic_values[field_key])


def _department_demo_row(row):
    if len(row) == 2:
        name, parent_name = row
        return name, parent_name, False
    return row


def _set_partner_field_value(field_value, field_type, value):
    field_value.value_text = None
    field_value.value_number = None
    field_value.value_date = None
    field_value.value_boolean = None
    field_value.value_json = None
    if field_type in {"text", "textarea", "select"}:
        field_value.value_text = str(value)
    elif field_type == "number":
        field_value.value_number = Decimal(str(value))
    elif field_type == "date":
        field_value.value_date = date.fromisoformat(str(value))
    elif field_type == "multi_select":
        field_value.value_json = list(value)


def _is_demo_department_head(full_name, position):
    manager_names = {manager_name for manager_name, _subordinate_name in RELATIONSHIP_DEMOS}
    keywords = ["Tổng giám đốc", "Giám đốc", "Trưởng", "Phụ trách", "Quản lý"]
    return full_name in manager_names or any(keyword in (position or "") for keyword in keywords)
