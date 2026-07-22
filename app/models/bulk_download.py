from app.extensions import db
from app.models.mixins import TimestampMixin
from app.models.storage import STORAGE_ID


class BulkDownloadJob(TimestampMixin, db.Model):
    __tablename__ = "bulk_download_jobs"
    __table_args__ = (
        db.CheckConstraint("module IN ('document-library', 'company-media')", name="ck_bulk_download_jobs_module"),
        db.CheckConstraint("status IN ('pending', 'running', 'succeeded', 'failed', 'expired')", name="ck_bulk_download_jobs_status"),
        db.Index("idx_bulk_download_jobs_status_expiry", "status", "expires_at"),
        db.Index("idx_bulk_download_jobs_requester_created", "requested_by_id", "created_at"),
    )
    id = db.Column(STORAGE_ID, primary_key=True)
    module = db.Column(db.String(40), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending", server_default="pending")
    requested_by_id = db.Column(STORAGE_ID, db.ForeignKey("users.id"), nullable=False)
    source_context_type = db.Column(db.String(20), nullable=False)
    source_context_id = db.Column(STORAGE_ID, nullable=False)
    requested_file_ids = db.Column(db.JSON, nullable=False)
    file_count = db.Column(db.Integer, nullable=False)
    completed_file_count = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    total_size_bytes = db.Column(db.BigInteger, nullable=False)
    zip_object_key = db.Column(db.String(1024), nullable=True)
    zip_size_bytes = db.Column(db.BigInteger, nullable=True)
    zip_filename = db.Column(db.String(255), nullable=False)
    error_message = db.Column(db.Text, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    requested_by = db.relationship("User", foreign_keys=[requested_by_id])
