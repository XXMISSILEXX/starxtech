from app.extensions import db
from app.models.enums import IssueSeverity, IssueStatus
from app.models.mixins import SoftDeleteMixin, TimestampMixin


class PersistentIssue(TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "persistent_issues"
    __table_args__ = (
        db.CheckConstraint(
            "severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_persistent_issues_severity",
        ),
        db.CheckConstraint(
            "status IN ('OPEN', 'PROCESSING', 'RESOLVED', 'CLOSED')",
            name="ck_persistent_issues_status",
        ),
        db.Index("idx_issues_project_status", "project_id", "status"),
    )

    id = db.Column(db.BigInteger, primary_key=True)
    project_id = db.Column(
        db.BigInteger,
        db.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    severity = db.Column(
        db.String(50),
        nullable=False,
        default=IssueSeverity.MEDIUM.value,
        server_default=IssueSeverity.MEDIUM.value,
    )
    status = db.Column(
        db.String(50),
        nullable=False,
        default=IssueStatus.OPEN.value,
        server_default=IssueStatus.OPEN.value,
    )
    opened_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date, nullable=True)
    closed_date = db.Column(db.Date, nullable=True)
    created_by_user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)

    project = db.relationship("Project", back_populates="persistent_issues")
    created_by = db.relationship(
        "User",
        back_populates="created_issues",
        foreign_keys=[created_by_user_id],
    )
    sections = db.relationship(
        "PersistentIssueSection",
        primaryjoin=lambda: db.and_(
            PersistentIssue.id == PersistentIssueSection.persistent_issue_id,
            PersistentIssueSection.deleted_at.is_(None),
        ),
        back_populates="persistent_issue",
        cascade="all, delete-orphan",
        order_by=lambda: (PersistentIssueSection.sort_order, PersistentIssueSection.id),
    )


class PersistentIssueSection(TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "persistent_issue_sections"
    __table_args__ = (
        db.UniqueConstraint(
            "persistent_issue_id",
            "report_category_id",
            name="uq_persistent_issue_sections_issue_category",
        ),
        db.CheckConstraint(
            "severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_persistent_issue_sections_severity",
        ),
        db.CheckConstraint(
            "status IN ('OPEN', 'PROCESSING', 'RESOLVED', 'CLOSED')",
            name="ck_persistent_issue_sections_status",
        ),
        db.Index(
            "idx_persistent_issue_sections_persistent_issue_id",
            "persistent_issue_id",
        ),
        db.Index(
            "idx_persistent_issue_sections_report_category_id",
            "report_category_id",
        ),
    )

    id = db.Column(
        db.BigInteger().with_variant(db.Integer(), "sqlite"),
        primary_key=True,
    )
    persistent_issue_id = db.Column(
        db.BigInteger,
        db.ForeignKey("persistent_issues.id", ondelete="CASCADE"),
        nullable=False,
    )
    report_category_id = db.Column(
        db.BigInteger,
        db.ForeignKey("report_categories.id"),
        nullable=False,
    )
    severity = db.Column(
        db.String(50),
        nullable=False,
        default=IssueSeverity.MEDIUM.value,
        server_default=IssueSeverity.MEDIUM.value,
    )
    status = db.Column(
        db.String(50),
        nullable=False,
        default=IssueStatus.OPEN.value,
        server_default=IssueStatus.OPEN.value,
    )
    due_date = db.Column(db.Date, nullable=True)
    owner_user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)
    description = db.Column(db.Text, nullable=True)
    proposed_solution = db.Column(db.Text, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    created_by_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)
    updated_by_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)

    persistent_issue = db.relationship("PersistentIssue", back_populates="sections")
    report_category = db.relationship("ReportCategory")
    owner = db.relationship("User", foreign_keys=[owner_user_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    updated_by = db.relationship("User", foreign_keys=[updated_by_id])
