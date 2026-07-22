"""strict upload selections, quota events and legacy ZIP size

Revision ID: 20260722_0017
Revises: 20260722_0016
"""
from alembic import op
import sqlalchemy as sa

revision = "20260722_0017"
down_revision = "20260722_0016"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("upload_selection_sessions", sa.Column("id", sa.BigInteger(), primary_key=True), sa.Column("module_type", sa.String(40), nullable=False), sa.Column("target_type", sa.String(20), nullable=False), sa.Column("target_id", sa.BigInteger(), nullable=False), sa.Column("created_by_id", sa.BigInteger(), nullable=False), sa.Column("declared_files", sa.Integer(), nullable=False), sa.Column("declared_size_bytes", sa.BigInteger(), nullable=False), sa.Column("presigned_files", sa.Integer(), nullable=False, server_default="0"), sa.Column("presigned_size_bytes", sa.BigInteger(), nullable=False, server_default="0"), sa.Column("status", sa.String(20), nullable=False, server_default="pending"), sa.Column("expires_at", sa.DateTime(), nullable=False), sa.Column("completed_at", sa.DateTime()), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")), sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")), sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_upload_selection_sessions_created_by"))
    op.create_index("idx_upload_selection_owner_expiry", "upload_selection_sessions", ["created_by_id", "expires_at"])
    with op.batch_alter_table("upload_batches") as batch:
        batch.add_column(sa.Column("selection_session_id", sa.BigInteger(), nullable=True)); batch.create_foreign_key("fk_upload_batches_selection_session", "upload_selection_sessions", ["selection_session_id"], ["id"]); batch.create_index("ix_upload_batches_selection_session_id", ["selection_session_id"])
    op.create_table("download_events", sa.Column("id", sa.BigInteger(), primary_key=True), sa.Column("user_id", sa.BigInteger(), nullable=False), sa.Column("storage_object_id", sa.BigInteger()), sa.Column("derivative_id", sa.BigInteger()), sa.Column("kind", sa.String(30), nullable=False), sa.Column("estimated_bytes", sa.BigInteger(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")), sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_download_events_user"), sa.ForeignKeyConstraint(["storage_object_id"], ["storage_objects.id"], name="fk_download_events_storage_object"), sa.ForeignKeyConstraint(["derivative_id"], ["storage_derivatives.id"], name="fk_download_events_derivative"))
    op.create_index("idx_download_events_user_created", "download_events", ["user_id", "created_at"])
    with op.batch_alter_table("bulk_download_jobs") as batch: batch.add_column(sa.Column("zip_size_bytes", sa.BigInteger(), nullable=True))

def downgrade():
    with op.batch_alter_table("bulk_download_jobs") as batch: batch.drop_column("zip_size_bytes")
    op.drop_table("download_events")
    with op.batch_alter_table("upload_batches") as batch:
        batch.drop_index("ix_upload_batches_selection_session_id"); batch.drop_constraint("fk_upload_batches_selection_session", type_="foreignkey"); batch.drop_column("selection_session_id")
    op.drop_table("upload_selection_sessions")
