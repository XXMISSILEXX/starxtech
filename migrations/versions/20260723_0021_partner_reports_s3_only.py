"""enforce S3-only daily report attachments

Revision ID: 20260723_0021
Revises: 20260723_0020
"""
from alembic import op
import sqlalchemy as sa

revision = "20260723_0021"
down_revision = "20260723_0020"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    pending = bind.execute(sa.text("SELECT count(*) FROM report_attachments WHERE deleted_at IS NULL AND storage_object_id IS NULL")).scalar()
    if pending:
        raise RuntimeError("Còn ReportAttachment active chưa có StorageObject. Chạy flask dev-report-attachments-s3 --dry-run/--apply hoặc --clear-missing trước khi upgrade 0021.")
    with op.batch_alter_table("report_attachments") as batch:
        batch.create_check_constraint("ck_report_attachments_active_storage_object", "deleted_at IS NOT NULL OR storage_object_id IS NOT NULL")
        batch.drop_column("file_path")
        batch.drop_column("stored_filename")


def downgrade():
    with op.batch_alter_table("report_attachments") as batch:
        batch.add_column(sa.Column("stored_filename", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("file_path", sa.Text(), nullable=True))
        batch.drop_constraint("ck_report_attachments_active_storage_object", type_="check")
