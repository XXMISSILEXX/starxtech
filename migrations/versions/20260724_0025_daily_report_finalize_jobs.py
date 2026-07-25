"""record finalized daily-report items and make media jobs idempotent

Revision ID: 20260724_0025
Revises: 20260724_0024
"""
from alembic import op
import sqlalchemy as sa


revision = "20260724_0025"
down_revision = "20260724_0024"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("upload_batch_items") as batch:
        batch.add_column(sa.Column("finalized_at", sa.DateTime(), nullable=True))
    with op.batch_alter_table("media_processing_jobs") as batch:
        # Earlier versions used application-level idempotency only.  Preserve
        # deployability for databases that accumulated a duplicate pending row.
        op.execute("UPDATE storage_derivatives SET created_by_job_id = NULL WHERE created_by_job_id IN (SELECT id FROM media_processing_jobs WHERE id NOT IN (SELECT MIN(id) FROM media_processing_jobs GROUP BY storage_object_id, job_type))")
        op.execute("DELETE FROM media_processing_jobs WHERE id NOT IN (SELECT MIN(id) FROM media_processing_jobs GROUP BY storage_object_id, job_type)")
        batch.create_unique_constraint(
            "uq_media_jobs_storage_object_type",
            ["storage_object_id", "job_type"],
        )


def downgrade():
    with op.batch_alter_table("media_processing_jobs") as batch:
        batch.drop_constraint("uq_media_jobs_storage_object_type", type_="unique")
    with op.batch_alter_table("upload_batch_items") as batch:
        batch.drop_column("finalized_at")
