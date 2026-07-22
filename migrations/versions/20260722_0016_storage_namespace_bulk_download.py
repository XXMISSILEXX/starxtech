"""add module storage namespace and temporary bulk ZIP jobs

Revision ID: 20260722_0016
Revises: 20260722_0015
"""
from alembic import op
import sqlalchemy as sa

revision = "20260722_0016"
down_revision = "20260722_0015"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("storage_objects") as batch:
        batch.add_column(sa.Column("storage_module", sa.String(40), nullable=True))
        batch.create_index("ix_storage_objects_storage_module", ["storage_module"])
    op.create_table(
        "bulk_download_jobs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("module", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("requested_by_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source_context_type", sa.String(20), nullable=False),
        sa.Column("source_context_id", sa.BigInteger(), nullable=False),
        sa.Column("requested_file_ids", sa.JSON(), nullable=False),
        sa.Column("file_count", sa.Integer(), nullable=False),
        sa.Column("completed_file_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("zip_object_key", sa.String(1024)), sa.Column("zip_filename", sa.String(255), nullable=False),
        sa.Column("error_message", sa.Text()), sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime()), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")), sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("module IN ('document-library', 'company-media')", name="ck_bulk_download_jobs_module"),
        sa.CheckConstraint("status IN ('pending', 'running', 'succeeded', 'failed', 'expired')", name="ck_bulk_download_jobs_status"),
    )
    op.create_index("idx_bulk_download_jobs_status_expiry", "bulk_download_jobs", ["status", "expires_at"])
    op.create_index("idx_bulk_download_jobs_requester_created", "bulk_download_jobs", ["requested_by_id", "created_at"])


def downgrade():
    op.drop_table("bulk_download_jobs")
    with op.batch_alter_table("storage_objects") as batch:
        batch.drop_index("ix_storage_objects_storage_module")
        batch.drop_column("storage_module")
