from app.extensions import db
from app.models.mixins import CreatedAtMixin, SoftDeleteMixin, TimestampMixin


STORAGE_ID = db.BigInteger().with_variant(db.Integer(), "sqlite")


class StorageObject(CreatedAtMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "storage_objects"
    __table_args__ = (
        db.UniqueConstraint("bucket", "object_key", name="uq_storage_objects_bucket_key"),
        db.CheckConstraint("upload_status IN ('pending', 'uploaded', 'active', 'failed', 'deleted')", name="ck_storage_objects_upload_status"),
        db.CheckConstraint("processing_status IN ('none', 'queued', 'processing', 'completed', 'failed')", name="ck_storage_objects_processing_status"),
        db.Index("idx_storage_objects_upload_status_created", "upload_status", "created_at"),
        db.Index("idx_storage_objects_processing_status_created", "processing_status", "created_at"),
        db.Index("idx_storage_objects_uploader_status", "uploaded_by_id", "upload_status"),
        db.Index("idx_storage_objects_created", "created_at"),
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
        db.CheckConstraint("module_type IN ('project_documents', 'company_media', 'daily_reports')", name="ck_upload_batches_module_type"),
        db.CheckConstraint("target_type IN ('folder', 'album', 'project')", name="ck_upload_batches_target_type"),
        db.CheckConstraint("status IN ('pending', 'uploading', 'completed', 'partial_failed', 'failed')", name="ck_upload_batches_status"),
        db.Index("idx_upload_batches_creator_status", "created_by_id", "status"),
        db.Index("idx_upload_batches_target", "module_type", "target_type", "target_id"),
    )

    id = db.Column(STORAGE_ID, primary_key=True)
    module_type = db.Column(db.String(40), nullable=False)
    target_type = db.Column(db.String(20), nullable=False)
    target_id = db.Column(db.BigInteger, nullable=False)
    created_by_id = db.Column(STORAGE_ID, db.ForeignKey("users.id"), nullable=False, index=True)
    selection_session_id = db.Column(STORAGE_ID, db.ForeignKey("upload_selection_sessions.id"), nullable=True, index=True)
    total_files = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    accepted_files = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    completed_files = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    failed_files = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    status = db.Column(db.String(20), nullable=False, default="pending", server_default="pending")
    completed_at = db.Column(db.DateTime, nullable=True)

    created_by = db.relationship("User", foreign_keys=[created_by_id])
    items = db.relationship("UploadBatchItem", back_populates="upload_batch", cascade="all, delete-orphan")


class UploadSelectionSession(TimestampMixin, db.Model):
    __tablename__ = "upload_selection_sessions"
    __table_args__ = (db.CheckConstraint("module_type IN ('project_documents', 'company_media', 'daily_reports')", name="ck_upload_selection_module"),
                      db.CheckConstraint("target_type IN ('folder', 'album', 'project')", name="ck_upload_selection_target"),
                      db.CheckConstraint("status IN ('pending', 'uploading', 'ready', 'completed', 'finalized', 'cancelled', 'expired')", name="ck_upload_selection_status"),
                      db.Index("idx_upload_selection_owner_expiry", "created_by_id", "expires_at"),
                      db.Index("idx_upload_selection_project_status_expiry", "target_id", "status", "expires_at"))
    id = db.Column(STORAGE_ID, primary_key=True)
    module_type = db.Column(db.String(40), nullable=False); target_type = db.Column(db.String(20), nullable=False)
    target_id = db.Column(db.BigInteger, nullable=False); created_by_id = db.Column(STORAGE_ID, db.ForeignKey("users.id"), nullable=False)
    declared_files = db.Column(db.Integer, nullable=False); declared_size_bytes = db.Column(db.BigInteger, nullable=False)
    presigned_files = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    presigned_size_bytes = db.Column(db.BigInteger, nullable=False, default=0, server_default="0")
    status = db.Column(db.String(20), nullable=False, default="pending", server_default="pending")
    expires_at = db.Column(db.DateTime, nullable=False); completed_at = db.Column(db.DateTime)
    # Phase 5 records that the database-only cleanup has already removed every
    # disposable unfinished item. Completed items intentionally remain.
    cleaned_at = db.Column(db.DateTime, nullable=True)
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    batches = db.relationship("UploadBatch", foreign_keys=[UploadBatch.selection_session_id])


class DownloadEvent(CreatedAtMixin, db.Model):
    __tablename__ = "download_events"
    __table_args__ = (
        db.Index("idx_download_events_user_created", "user_id", "created_at"),
        db.Index("idx_download_events_created", "created_at"),
        db.Index("idx_download_events_module_created", "module", "created_at"),
        db.Index("idx_download_events_object_created", "storage_object_id", "created_at"),
        db.Index("idx_download_events_source_type_created", "source_type", "created_at"),
    )
    id = db.Column(STORAGE_ID, primary_key=True); user_id = db.Column(STORAGE_ID, db.ForeignKey("users.id"), nullable=False)
    storage_object_id = db.Column(STORAGE_ID, db.ForeignKey("storage_objects.id")); derivative_id = db.Column(STORAGE_ID, db.ForeignKey("storage_derivatives.id"))
    kind = db.Column(db.String(30), nullable=False); source_type = db.Column(db.String(30), nullable=True)
    module = db.Column(db.String(40), nullable=True)
    estimated_bytes = db.Column(db.BigInteger, nullable=False)
    estimated_storage_egress_bytes = db.Column(db.BigInteger, nullable=True)
    estimated_client_egress_bytes = db.Column(db.BigInteger, nullable=True)


class UploadBatchItem(TimestampMixin, db.Model):
    __tablename__ = "upload_batch_items"
    __table_args__ = (
        db.UniqueConstraint("upload_batch_id", "client_file_id", name="uq_upload_batch_items_client_file"),
        db.UniqueConstraint("selection_session_id", "client_file_id", name="uq_upload_batch_items_selection_client_file"),
        db.CheckConstraint("status IN ('accepted', 'rejected', 'uploading', 'completed', 'failed', 'cancelled')", name="ck_upload_batch_items_status"),
        db.Index("idx_upload_batch_items_batch_status", "upload_batch_id", "status"),
        db.Index("idx_upload_batch_items_storage_object", "storage_object_id"),
        db.Index("idx_upload_batch_items_client_section", "upload_batch_id", "client_section_id"),
    )

    id = db.Column(STORAGE_ID, primary_key=True)
    upload_batch_id = db.Column(STORAGE_ID, db.ForeignKey("upload_batches.id", ondelete="CASCADE"), nullable=False)
    # This is deliberately direct.  The parent batch is only a request grouping
    # and therefore cannot be the durable idempotency scope for a selection.
    selection_session_id = db.Column(STORAGE_ID, db.ForeignKey("upload_selection_sessions.id"), nullable=True, index=True)
    storage_object_id = db.Column(STORAGE_ID, db.ForeignKey("storage_objects.id"), nullable=True)
    client_file_id = db.Column(db.String(255), nullable=False)
    client_section_id = db.Column(db.String(80), nullable=True)
    original_filename = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.BigInteger, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    error_message = db.Column(db.Text, nullable=True)
    # An item remains `completed` after it is consumed so the upload audit trail
    # stays truthful; this timestamp prevents it being attached twice.
    finalized_at = db.Column(db.DateTime, nullable=True)

    upload_batch = db.relationship("UploadBatch", back_populates="items")
    selection_session = db.relationship("UploadSelectionSession", foreign_keys=[selection_session_id])
    storage_object = db.relationship("StorageObject", back_populates="batch_items")
