from app.extensions import db
from app.models.mixins import CreatedAtMixin, SoftDeleteMixin, TimestampMixin


STORAGE_ID = db.BigInteger().with_variant(db.Integer(), "sqlite")


class StorageObject(CreatedAtMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "storage_objects"
    __table_args__ = (
        db.UniqueConstraint("bucket", "object_key", name="uq_storage_objects_bucket_key"),
        db.CheckConstraint("upload_status IN ('pending', 'active', 'failed', 'deleted')", name="ck_storage_objects_upload_status"),
        db.CheckConstraint("processing_status IN ('none', 'queued', 'processing', 'completed', 'failed')", name="ck_storage_objects_processing_status"),
        db.Index("idx_storage_objects_upload_status_created", "upload_status", "created_at"),
        db.Index("idx_storage_objects_processing_status_created", "processing_status", "created_at"),
        db.Index("idx_storage_objects_uploader_status", "uploaded_by_id", "upload_status"),
    )

    id = db.Column(STORAGE_ID, primary_key=True)
    bucket = db.Column(db.String(255), nullable=False)
    object_key = db.Column(db.String(1024), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(255), nullable=False)
    file_ext = db.Column(db.String(20), nullable=False)
    file_size = db.Column(db.BigInteger, nullable=False)
    checksum_sha256 = db.Column(db.String(64), nullable=True)
    # Null means a legacy object: its persisted object_key remains canonical.
    storage_module = db.Column(db.String(40), nullable=True, index=True)
    width = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)
    duration_seconds = db.Column(db.Numeric(12, 3), nullable=True)
    uploaded_by_id = db.Column(STORAGE_ID, db.ForeignKey("users.id"), nullable=False, index=True)
    upload_status = db.Column(db.String(20), nullable=False, default="pending", server_default="pending")
    processing_status = db.Column(db.String(20), nullable=False, default="none", server_default="none")
    completed_at = db.Column(db.DateTime, nullable=True)

    uploaded_by = db.relationship("User", foreign_keys=[uploaded_by_id])
    batch_items = db.relationship("UploadBatchItem", back_populates="storage_object")


class UploadBatch(CreatedAtMixin, db.Model):
    __tablename__ = "upload_batches"
    __table_args__ = (
        db.CheckConstraint("module_type IN ('project_documents', 'company_media')", name="ck_upload_batches_module_type"),
        db.CheckConstraint("target_type IN ('folder', 'album')", name="ck_upload_batches_target_type"),
        db.CheckConstraint("status IN ('pending', 'uploading', 'completed', 'partial_failed', 'failed')", name="ck_upload_batches_status"),
        db.Index("idx_upload_batches_creator_status", "created_by_id", "status"),
        db.Index("idx_upload_batches_target", "module_type", "target_type", "target_id"),
    )

    id = db.Column(STORAGE_ID, primary_key=True)
    module_type = db.Column(db.String(40), nullable=False)
    target_type = db.Column(db.String(20), nullable=False)
    target_id = db.Column(db.BigInteger, nullable=False)
    created_by_id = db.Column(STORAGE_ID, db.ForeignKey("users.id"), nullable=False, index=True)
    total_files = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    accepted_files = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    completed_files = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    failed_files = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    status = db.Column(db.String(20), nullable=False, default="pending", server_default="pending")
    completed_at = db.Column(db.DateTime, nullable=True)

    created_by = db.relationship("User", foreign_keys=[created_by_id])
    items = db.relationship("UploadBatchItem", back_populates="upload_batch", cascade="all, delete-orphan")


class UploadBatchItem(TimestampMixin, db.Model):
    __tablename__ = "upload_batch_items"
    __table_args__ = (
        db.UniqueConstraint("upload_batch_id", "client_file_id", name="uq_upload_batch_items_client_file"),
        db.CheckConstraint("status IN ('accepted', 'rejected', 'uploading', 'completed', 'failed', 'cancelled')", name="ck_upload_batch_items_status"),
        db.Index("idx_upload_batch_items_batch_status", "upload_batch_id", "status"),
        db.Index("idx_upload_batch_items_storage_object", "storage_object_id"),
    )

    id = db.Column(STORAGE_ID, primary_key=True)
    upload_batch_id = db.Column(STORAGE_ID, db.ForeignKey("upload_batches.id", ondelete="CASCADE"), nullable=False)
    storage_object_id = db.Column(STORAGE_ID, db.ForeignKey("storage_objects.id"), nullable=True)
    client_file_id = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.BigInteger, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    error_message = db.Column(db.Text, nullable=True)

    upload_batch = db.relationship("UploadBatch", back_populates="items")
    storage_object = db.relationship("StorageObject", back_populates="batch_items")
