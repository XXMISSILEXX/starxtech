from app.extensions import db
from app.models.enums import ProjectContractorAssignmentStatus, ProjectContractorRole
from app.models.mixins import TimestampMixin


class ProjectContractor(TimestampMixin, db.Model):
    """An independent catalog entry for a contractor working on projects.

    This deliberately has no relationship to the Partner/Company domain.
    """

    __tablename__ = "project_contractors"
    __table_args__ = (
        db.Index(
            "uq_project_contractors_active_normalized_name",
            "normalized_name",
            unique=True,
            postgresql_where=db.text("is_active"),
            sqlite_where=db.text("is_active"),
        ),
        db.Index("ix_project_contractors_is_active", "is_active"),
        db.Index("ix_project_contractors_normalized_name", "normalized_name"),
    )

    id = db.Column(db.BigInteger().with_variant(db.Integer(), "sqlite"), primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    normalized_name = db.Column(db.String(255), nullable=False)
    short_name = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    address = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    archived_at = db.Column(db.DateTime, nullable=True)
    created_by_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)
    updated_by_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)

    created_by = db.relationship("User", foreign_keys=[created_by_id])
    updated_by = db.relationship("User", foreign_keys=[updated_by_id])
    assignments = db.relationship("ProjectContractorAssignment", back_populates="contractor")


class ProjectContractorAssignment(TimestampMixin, db.Model):
    __tablename__ = "project_contractor_assignments"
    __table_args__ = (
        db.CheckConstraint(
            "role IN ('CONSTRUCTION', 'SOLUTION')",
            name="ck_project_contractor_assignments_role",
        ),
        db.CheckConstraint(
            "status IN ('ACTIVE', 'PAUSED', 'COMPLETED', 'ENDED')",
            name="ck_project_contractor_assignments_status",
        ),
        db.Index(
            "uq_project_contractor_assignments_open_role",
            "project_id",
            "contractor_id",
            "role",
            unique=True,
            postgresql_where=db.text("status != 'ENDED'"),
            sqlite_where=db.text("status != 'ENDED'"),
        ),
        db.Index("ix_project_contractor_assignments_project_role", "project_id", "role"),
    )

    id = db.Column(db.BigInteger().with_variant(db.Integer(), "sqlite"), primary_key=True)
    project_id = db.Column(
        db.BigInteger,
        db.ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    contractor_id = db.Column(
        db.BigInteger,
        db.ForeignKey("project_contractors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    role = db.Column(
        db.String(20),
        nullable=False,
        default=ProjectContractorRole.CONSTRUCTION.value,
        server_default=ProjectContractorRole.CONSTRUCTION.value,
    )
    status = db.Column(
        db.String(20),
        nullable=False,
        default=ProjectContractorAssignmentStatus.ACTIVE.value,
        server_default=ProjectContractorAssignmentStatus.ACTIVE.value,
    )
    started_on = db.Column(db.Date, nullable=True)
    ended_on = db.Column(db.Date, nullable=True)
    note = db.Column(db.Text, nullable=True)
    created_by_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)
    updated_by_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)

    project = db.relationship("Project", back_populates="contractor_assignments")
    contractor = db.relationship("ProjectContractor", back_populates="assignments")
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    updated_by = db.relationship("User", foreign_keys=[updated_by_id])
    updates = db.relationship("ProjectUpdate", back_populates="contractor_assignment")
