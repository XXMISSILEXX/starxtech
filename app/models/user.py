from flask_login import UserMixin
from werkzeug.security import check_password_hash

from app.extensions import db
from app.models.mixins import SoftDeleteMixin, TimestampMixin


DEFAULT_UI_PREFERENCES = {"appearance": "system", "accent": "blue"}


class User(UserMixin, TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "users"
    # `role_id` is canonical.  The old column remains a compatibility mirror
    # until external consumers have migrated, and is never authorization input.
    __table_args__ = ()

    id = db.Column(db.BigInteger, primary_key=True)
    full_name = db.Column(db.String(255), nullable=False)
    username = db.Column(db.String(100), nullable=False, unique=True, index=True)
    email = db.Column(db.String(255), nullable=True, unique=True, index=True)
    password_hash = db.Column(db.Text, nullable=False)
    # Retained for one release only so existing databases can be migrated safely.
    legacy_role = db.Column("role", db.String(50), nullable=True)
    role_id = db.Column(db.BigInteger().with_variant(db.Integer(), "sqlite"), db.ForeignKey("roles.id"), nullable=False, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    last_login_at = db.Column(db.DateTime, nullable=True)
    avatar_storage_object_id = db.Column(
        db.BigInteger,
        db.ForeignKey("storage_objects.id", name="fk_users_avatar_storage_object_id", ondelete="SET NULL", use_alter=True),
        nullable=True,
        index=True,
    )
    # Personal display preferences are deliberately kept with the user record:
    # the database is canonical, while the browser cache is only a paint aid.
    ui_preferences = db.Column(
        db.JSON,
        nullable=False,
        default=lambda: dict(DEFAULT_UI_PREFERENCES),
        server_default='{"appearance":"system","accent":"blue"}',
    )
    role = db.relationship("Role", back_populates="users")
    avatar_storage_object = db.relationship("StorageObject", foreign_keys=[avatar_storage_object_id])

    project_assignments = db.relationship(
        "ProjectUser",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    created_projects = db.relationship(
        "Project",
        back_populates="created_by",
        foreign_keys="Project.created_by_user_id",
    )
    created_reports = db.relationship(
        "DailyReport",
        back_populates="created_by",
        foreign_keys="DailyReport.created_by_user_id",
    )
    updated_reports = db.relationship(
        "DailyReport",
        back_populates="updated_by",
        foreign_keys="DailyReport.updated_by_user_id",
    )
    uploaded_attachments = db.relationship(
        "ReportAttachment",
        back_populates="uploaded_by",
        foreign_keys="ReportAttachment.uploaded_by_user_id",
    )
    owned_issues = db.relationship(
        "PersistentIssue",
        back_populates="owner",
        foreign_keys="PersistentIssue.owner_user_id",
    )
    created_issues = db.relationship(
        "PersistentIssue",
        back_populates="created_by",
        foreign_keys="PersistentIssue.created_by_user_id",
    )
    audit_logs = db.relationship(
        "AuditLog",
        back_populates="actor",
        foreign_keys="AuditLog.actor_user_id",
    )

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def role_code(self):
        return self.role.code if self.role is not None else None

    def has_role(self, code):
        return self.role_code == code

    def can(self, code):
        from app.permissions.services import user_has_permission

        return user_has_permission(self, code)
