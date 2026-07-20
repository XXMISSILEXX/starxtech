from app.extensions import db
from app.models.mixins import CreatedAtMixin, SoftDeleteMixin, TimestampMixin
from app.models.storage import STORAGE_ID

class StorageDerivative(CreatedAtMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "storage_derivatives"
    __table_args__ = (db.UniqueConstraint("bucket", "object_key", name="uq_storage_derivatives_bucket_key"), db.CheckConstraint("derivative_type IN ('thumbnail','preview','poster','video_preview')", name="ck_storage_derivatives_type"), db.Index("idx_storage_derivatives_object_type", "storage_object_id", "derivative_type"))
    id = db.Column(STORAGE_ID, primary_key=True)
    storage_object_id = db.Column(STORAGE_ID, db.ForeignKey("storage_objects.id"), nullable=False)
    derivative_type = db.Column(db.String(30), nullable=False)
    bucket = db.Column(db.String(255), nullable=False); object_key = db.Column(db.String(1024), nullable=False)
    mime_type = db.Column(db.String(255), nullable=False); file_ext = db.Column(db.String(20), nullable=False); file_size = db.Column(db.BigInteger, nullable=False)
    width = db.Column(db.Integer); height = db.Column(db.Integer); duration_seconds = db.Column(db.Numeric(12,3)); created_by_job_id = db.Column(STORAGE_ID, db.ForeignKey("media_processing_jobs.id"), nullable=True)

class MediaProcessingJob(TimestampMixin, db.Model):
    __tablename__ = "media_processing_jobs"
    __table_args__ = (db.CheckConstraint("job_type IN ('image_derivatives','video_derivatives')", name="ck_media_jobs_type"), db.CheckConstraint("status IN ('pending','processing','succeeded','failed','cancelled')", name="ck_media_jobs_status"), db.Index("idx_media_jobs_status_created", "status", "created_at"), db.Index("idx_media_jobs_object_type", "storage_object_id", "job_type"))
    id = db.Column(STORAGE_ID, primary_key=True); storage_object_id = db.Column(STORAGE_ID, db.ForeignKey("storage_objects.id"), nullable=False)
    job_type = db.Column(db.String(40), nullable=False); status = db.Column(db.String(20), nullable=False, default="pending"); celery_task_id = db.Column(db.String(255))
    attempts = db.Column(db.Integer, nullable=False, default=0); max_attempts = db.Column(db.Integer, nullable=False, default=3)
    started_at = db.Column(db.DateTime); finished_at = db.Column(db.DateTime); error_code = db.Column(db.String(100)); error_message = db.Column(db.Text)
    storage_object = db.relationship("StorageObject")
