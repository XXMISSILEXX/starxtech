from app.extensions import db
from app.models.enums import DailyReportStatus, SectionStatus
from app.models.mixins import CreatedAtMixin, SoftDeleteMixin, TimestampMixin


class DailyReport(TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "daily_reports"
    __table_args__ = (
        db.UniqueConstraint("project_id", "report_date", name="uq_daily_reports_project_date"),
        db.CheckConstraint(
            "overall_status IN ('UPDATED', 'GOOD', 'PROCESSING', 'ATTENTION', 'CRITICAL')",
            name="ck_daily_reports_overall_status",
        ),
        db.Index("idx_daily_reports_project_date", "project_id", "report_date"),
        db.Index("idx_daily_reports_status", "overall_status"),
    )

    id = db.Column(db.BigInteger, primary_key=True)
    project_id = db.Column(
        db.BigInteger,
        db.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    report_date = db.Column(db.Date, nullable=False)
    overall_status = db.Column(
        db.String(50),
        nullable=False,
        default=DailyReportStatus.UPDATED.value,
    )
    highlight = db.Column(db.Text, nullable=False)
    summary_note = db.Column(db.Text, nullable=True)
    created_by_user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)
    updated_by_user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)

    project = db.relationship("Project", back_populates="daily_reports")
    created_by = db.relationship(
        "User",
        back_populates="created_reports",
        foreign_keys=[created_by_user_id],
    )
    updated_by = db.relationship(
        "User",
        back_populates="updated_reports",
        foreign_keys=[updated_by_user_id],
    )
    sections = db.relationship(
        "DailyReportSection",
        back_populates="daily_report",
        cascade="all, delete-orphan",
    )


class DailyReportSection(TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "daily_report_sections"
    __table_args__ = (
        db.UniqueConstraint(
            "daily_report_id",
            "report_category_id",
            name="uq_daily_report_sections_report_category",
        ),
        db.CheckConstraint(
            "status IN ('INFO', 'GOOD', 'PROCESSING', 'ATTENTION', 'CRITICAL')",
            name="ck_daily_report_sections_status",
        ),
    )

    id = db.Column(db.BigInteger, primary_key=True)
    daily_report_id = db.Column(
        db.BigInteger,
        db.ForeignKey("daily_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_category_id = db.Column(
        db.BigInteger,
        db.ForeignKey("report_categories.id"),
        nullable=False,
        index=True,
    )
    status = db.Column(db.String(50), nullable=False, default=SectionStatus.INFO.value)
    content = db.Column(db.Text, nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0, server_default="0")

    daily_report = db.relationship("DailyReport", back_populates="sections")
    report_category = db.relationship("ReportCategory", back_populates="report_sections")
    attachments = db.relationship(
        "ReportAttachment",
        back_populates="section",
        cascade="all, delete-orphan",
    )


class ReportAttachment(CreatedAtMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "report_attachments"
    __table_args__ = (
        db.Index("idx_attachments_section", "daily_report_section_id"),
    )

    id = db.Column(db.BigInteger, primary_key=True)
    daily_report_section_id = db.Column(
        db.BigInteger,
        db.ForeignKey("daily_report_sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.Text, nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    file_size = db.Column(db.BigInteger, nullable=False)
    image_width = db.Column(db.Integer, nullable=True)
    image_height = db.Column(db.Integer, nullable=True)
    uploaded_by_user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)

    section = db.relationship("DailyReportSection", back_populates="attachments")
    uploaded_by = db.relationship(
        "User",
        back_populates="uploaded_attachments",
        foreign_keys=[uploaded_by_user_id],
    )
