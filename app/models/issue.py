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
    owner_user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)
    created_by_user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)

    project = db.relationship("Project", back_populates="persistent_issues")
    owner = db.relationship(
        "User",
        back_populates="owned_issues",
        foreign_keys=[owner_user_id],
    )
    created_by = db.relationship(
        "User",
        back_populates="created_issues",
        foreign_keys=[created_by_user_id],
    )
