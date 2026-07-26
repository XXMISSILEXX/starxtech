from app.extensions import db
from app.models.enums import ProjectUpdateType
from app.models.mixins import TimestampMixin


class ProjectUpdate(TimestampMixin, db.Model):
    __tablename__ = "project_updates"
    __table_args__ = (
        db.CheckConstraint(
            "update_type IN ('GENERAL', 'PROGRESS', 'HANDOVER', 'CONTRACTOR', 'STATUS_CHANGE', 'NOTE')",
            name="ck_project_updates_type",
        ),
        db.Index("ix_project_updates_project_date", "project_id", "update_date"),
        db.Index("ix_project_updates_assignment_date", "contractor_assignment_id", "update_date"),
    )

    id = db.Column(db.BigInteger().with_variant(db.Integer(), "sqlite"), primary_key=True)
    project_id = db.Column(db.BigInteger, db.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
    contractor_assignment_id = db.Column(db.BigInteger, db.ForeignKey("project_contractor_assignments.id", ondelete="RESTRICT"), nullable=True, index=True)
    update_type = db.Column(db.String(30), nullable=False, default=ProjectUpdateType.GENERAL.value, server_default=ProjectUpdateType.GENERAL.value)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    update_date = db.Column(db.Date, nullable=False, index=True)
    created_by_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)
    updated_by_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)

    project = db.relationship("Project", back_populates="updates")
    contractor_assignment = db.relationship("ProjectContractorAssignment", back_populates="updates")
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    updated_by = db.relationship("User", foreign_keys=[updated_by_id])
