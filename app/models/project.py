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
    created_by_user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)

    created_by = db.relationship(
        "User",
        back_populates="created_projects",
        foreign_keys=[created_by_user_id],
    )
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


class ProjectUser(CreatedAtMixin, db.Model):
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
    role_in_project = db.Column(
        db.String(50),
        nullable=False,
        default="REPORTER",
        server_default="REPORTER",
    )

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
