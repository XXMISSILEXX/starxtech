"""add direct upload lifecycle for daily reports

Revision ID: 20260724_0024
Revises: 20260724_0023
"""
from alembic import op
import sqlalchemy as sa

revision = "20260724_0024"
down_revision = "20260724_0023"
branch_labels = None
depends_on = None


def upgrade():
    # batch_alter keeps the migration usable in local SQLite test databases.
    with op.batch_alter_table("storage_objects") as batch:
        batch.drop_constraint("ck_storage_objects_upload_status", type_="check")
        batch.create_check_constraint("ck_storage_objects_upload_status", "upload_status IN ('pending', 'uploaded', 'active', 'failed', 'deleted')")
    with op.batch_alter_table("upload_batches") as batch:
        batch.drop_constraint("ck_upload_batches_module_type", type_="check")
        batch.drop_constraint("ck_upload_batches_target_type", type_="check")
        batch.create_check_constraint("ck_upload_batches_module_type", "module_type IN ('project_documents', 'company_media', 'daily_reports')")
        batch.create_check_constraint("ck_upload_batches_target_type", "target_type IN ('folder', 'album', 'project')")
    with op.batch_alter_table("upload_selection_sessions") as batch:
        # 0017 intentionally created this table without constraints, so there
        # are no legacy names to drop on deployed databases.
        batch.create_check_constraint("ck_upload_selection_module", "module_type IN ('project_documents', 'company_media', 'daily_reports')")
        batch.create_check_constraint("ck_upload_selection_target", "target_type IN ('folder', 'album', 'project')")
        batch.create_check_constraint("ck_upload_selection_status", "status IN ('pending', 'uploading', 'ready', 'completed', 'finalized', 'cancelled', 'expired')")
        batch.create_index("idx_upload_selection_project_status_expiry", ["target_id", "status", "expires_at"])
    with op.batch_alter_table("upload_batch_items") as batch:
        batch.add_column(sa.Column("client_section_id", sa.String(length=80), nullable=True))
        batch.create_index("idx_upload_batch_items_client_section", ["upload_batch_id", "client_section_id"])


def downgrade():
    with op.batch_alter_table("upload_batch_items") as batch:
        batch.drop_index("idx_upload_batch_items_client_section"); batch.drop_column("client_section_id")
    with op.batch_alter_table("upload_selection_sessions") as batch:
        batch.drop_index("idx_upload_selection_project_status_expiry")
        batch.drop_constraint("ck_upload_selection_module", type_="check")
        batch.drop_constraint("ck_upload_selection_target", type_="check")
        batch.drop_constraint("ck_upload_selection_status", type_="check")
    with op.batch_alter_table("upload_batches") as batch:
        batch.drop_constraint("ck_upload_batches_module_type", type_="check")
        batch.drop_constraint("ck_upload_batches_target_type", type_="check")
        batch.create_check_constraint("ck_upload_batches_module_type", "module_type IN ('project_documents', 'company_media')")
        batch.create_check_constraint("ck_upload_batches_target_type", "target_type IN ('folder', 'album')")
    with op.batch_alter_table("storage_objects") as batch:
        batch.drop_constraint("ck_storage_objects_upload_status", type_="check")
        batch.create_check_constraint("ck_storage_objects_upload_status", "upload_status IN ('pending', 'active', 'failed', 'deleted')")
