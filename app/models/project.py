from app.extensions import db
from app.models.enums import ProjectStatus
from app.models.mixins import CreatedAtMixin, SoftDeleteMixin, TimestampMixin


class Project(TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "projects"
    __table_args__ = (
        db.CheckConstraint(
            "status IN ('active', 'paused', 'completed', 'archived')",
            name="ck_projects_status",
        ),
    )

    id = db.Column(db.BigInteger, primary_key=True)
    code = db.Column(db.String(50), nullable=False, unique=True, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(
        db.String(50),
        nullable=False,
        default=ProjectStatus.ACTIVE.value,
        server_default=ProjectStatus.ACTIVE.value,
    )
    start_date = db.Column(db.Date, nullable=True)
    expected_end_date = db.Column(db.Date, nullable=True)
    customer_id = db.Column(
        db.BigInteger,
        db.ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    created_by_user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)

    created_by = db.relationship(
        "User",
        back_populates="created_projects",
        foreign_keys=[created_by_user_id],
    )
    customer = db.relationship("Customer", back_populates="projects")
    user_assignments = db.relationship(
        "ProjectUser",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    categories = db.relationship(
        "ReportCategory",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    daily_reports = db.relationship(
        "DailyReport",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    persistent_issues = db.relationship(
        "PersistentIssue",
        back_populates="project",
        cascade="all, delete-orphan",
    )


class ProjectUser(TimestampMixin, db.Model):
    __tablename__ = "project_users"
    __table_args__ = (
        db.UniqueConstraint("project_id", "user_id", name="uq_project_users_project_user"),
    )

    id = db.Column(db.BigInteger, primary_key=True)
    project_id = db.Column(
        db.BigInteger,
        db.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # A preset selected by administrators.  The capability flags below are the
    # authorization source of truth; this value is intentionally not checked by
    # request policies.
    project_role_code = db.Column(
        db.String(50),
        nullable=False,
        default="PROJECT_VIEWER",
        server_default="PROJECT_VIEWER",
    )
    # Backwards-compatible ORM spelling for callers not yet migrated.
    role_in_project = db.synonym("project_role_code")
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    can_view_project = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_view_reports = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_create_reports = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_edit_own_reports = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_edit_all_reports = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_archive_reports = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_view_issues = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_create_issues = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_edit_issues = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_close_reopen_issues = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_manage_report_categories = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_view_documents = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_upload_documents = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_edit_documents = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_share_documents = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_archive_documents = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_restore_documents = db.Column(db.Boolean, nullable=False, default=False, server_default="false")

    project = db.relationship("Project", back_populates="user_assignments")
    user = db.relationship("User", back_populates="project_assignments")


class ReportCategory(TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "report_categories"
    __table_args__ = (
        db.UniqueConstraint("project_id", "name", name="uq_report_categories_project_name"),
    )

    id = db.Column(db.BigInteger, primary_key=True)
    project_id = db.Column(
        db.BigInteger,
        db.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    icon = db.Column(db.String(50), nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    is_required = db.Column(db.Boolean, nullable=False, default=False, server_default="false")

    project = db.relationship("Project", back_populates="categories")
    report_sections = db.relationship("DailyReportSection", back_populates="report_category")
