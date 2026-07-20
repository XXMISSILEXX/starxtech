"""add storage batch foundation

Revision ID: 20260720_0010
Revises: 20260719_0009
Create Date: 2026-07-20
"""
from alembic import op
import sqlalchemy as sa


revision = "20260720_0010"
down_revision = "20260719_0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "storage_objects",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("bucket", sa.String(length=255), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("file_ext", sa.String(length=20), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64)),
        sa.Column("width", sa.Integer()), sa.Column("height", sa.Integer()), sa.Column("duration_seconds", sa.Numeric(12, 3)),
        sa.Column("uploaded_by_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("upload_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("processing_status", sa.String(length=20), nullable=False, server_default="none"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("completed_at", sa.DateTime()), sa.Column("deleted_at", sa.DateTime()),
        sa.UniqueConstraint("bucket", "object_key", name="uq_storage_objects_bucket_key"),
        sa.CheckConstraint("upload_status IN ('pending', 'active', 'failed', 'deleted')", name="ck_storage_objects_upload_status"),
        sa.CheckConstraint("processing_status IN ('none', 'queued', 'processing', 'completed', 'failed')", name="ck_storage_objects_processing_status"),
    )
    op.create_index("idx_storage_objects_upload_status_created", "storage_objects", ["upload_status", "created_at"])
    op.create_index("idx_storage_objects_processing_status_created", "storage_objects", ["processing_status", "created_at"])
    op.create_index("idx_storage_objects_uploader_status", "storage_objects", ["uploaded_by_id", "upload_status"])
    op.create_table(
        "upload_batches",
        sa.Column("id", sa.BigInteger(), primary_key=True), sa.Column("module_type", sa.String(length=40), nullable=False), sa.Column("target_type", sa.String(length=20), nullable=False), sa.Column("target_id", sa.BigInteger(), nullable=False),
        sa.Column("created_by_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("total_files", sa.Integer(), nullable=False, server_default="0"), sa.Column("accepted_files", sa.Integer(), nullable=False, server_default="0"), sa.Column("completed_files", sa.Integer(), nullable=False, server_default="0"), sa.Column("failed_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")), sa.Column("completed_at", sa.DateTime()),
        sa.CheckConstraint("module_type IN ('project_documents', 'company_media')", name="ck_upload_batches_module_type"), sa.CheckConstraint("target_type IN ('folder', 'album')", name="ck_upload_batches_target_type"), sa.CheckConstraint("status IN ('pending', 'uploading', 'completed', 'partial_failed', 'failed')", name="ck_upload_batches_status"),
    )
    op.create_index("idx_upload_batches_creator_status", "upload_batches", ["created_by_id", "status"])
    op.create_index("idx_upload_batches_target", "upload_batches", ["module_type", "target_type", "target_id"])
    op.create_table(
        "upload_batch_items",
        sa.Column("id", sa.BigInteger(), primary_key=True), sa.Column("upload_batch_id", sa.BigInteger(), sa.ForeignKey("upload_batches.id", ondelete="CASCADE"), nullable=False), sa.Column("storage_object_id", sa.BigInteger(), sa.ForeignKey("storage_objects.id")),
        sa.Column("client_file_id", sa.String(length=255), nullable=False), sa.Column("original_filename", sa.String(length=255), nullable=False), sa.Column("mime_type", sa.String(length=255), nullable=False), sa.Column("file_size", sa.BigInteger(), nullable=False), sa.Column("status", sa.String(length=20), nullable=False), sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")), sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("upload_batch_id", "client_file_id", name="uq_upload_batch_items_client_file"), sa.CheckConstraint("status IN ('accepted', 'rejected', 'uploading', 'completed', 'failed', 'cancelled')", name="ck_upload_batch_items_status"),
    )
    op.create_index("idx_upload_batch_items_batch_status", "upload_batch_items", ["upload_batch_id", "status"])
    op.create_index("idx_upload_batch_items_storage_object", "upload_batch_items", ["storage_object_id"])


def downgrade():
    op.drop_table("upload_batch_items")
    op.drop_table("upload_batches")
    op.drop_table("storage_objects")
