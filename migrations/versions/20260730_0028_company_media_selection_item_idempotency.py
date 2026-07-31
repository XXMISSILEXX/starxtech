"""add Company Media selection-scoped idempotency

Revision ID: 20260730_0028
Revises: 20260729_0027
"""

from alembic import op
import sqlalchemy as sa


revision = "20260730_0028"
down_revision = "20260729_0027"
branch_labels = None
depends_on = None


def _assert_preflight_clean(bind):
    """Fail closed; never pick a canonical legacy row or touch storage."""
    duplicate = bind.execute(sa.text("""
        SELECT 1
        FROM upload_batch_items AS i
        JOIN upload_batches AS b ON b.id = i.upload_batch_id
        WHERE b.selection_session_id IS NOT NULL
        GROUP BY b.selection_session_id, i.client_file_id
        HAVING COUNT(*) > 1
        LIMIT 1
    """)).first()
    if duplicate:
        raise RuntimeError(
            "Company Media idempotency preflight found duplicate "
            "(selection_session_id, client_file_id) rows; stop and resolve manually."
        )

    invalid_client_id = bind.execute(sa.text("""
        SELECT 1 FROM upload_batch_items
        WHERE client_file_id IS NULL OR trim(client_file_id) = '' OR length(client_file_id) > 255
        LIMIT 1
    """)).first()
    if invalid_client_id:
        raise RuntimeError("Company Media idempotency preflight found invalid client_file_id rows; stop and resolve manually.")

    reused_media_object = bind.execute(sa.text("""
        SELECT 1 FROM company_media_files
        GROUP BY storage_object_id
        HAVING COUNT(*) > 1
        LIMIT 1
    """)).first()
    if reused_media_object:
        raise RuntimeError("Company Media preflight found one StorageObject linked to multiple media rows; stop and resolve manually.")


def upgrade():
    bind = op.get_bind()
    _assert_preflight_clean(bind)
    with op.batch_alter_table("upload_batch_items") as batch:
        batch.add_column(sa.Column("selection_session_id", sa.BigInteger(), nullable=True))
        batch.create_foreign_key(
            "fk_upload_batch_items_selection_session",
            "upload_selection_sessions",
            ["selection_session_id"], ["id"],
        )
    bind.execute(sa.text("""
        UPDATE upload_batch_items
        SET selection_session_id = (
            SELECT upload_batches.selection_session_id
            FROM upload_batches
            WHERE upload_batches.id = upload_batch_items.upload_batch_id
        )
        WHERE selection_session_id IS NULL
    """))
    with op.batch_alter_table("upload_batch_items") as batch:
        batch.create_index("ix_upload_batch_items_selection_session_id", ["selection_session_id"])
        batch.create_unique_constraint(
            "uq_upload_batch_items_selection_client_file",
            ["selection_session_id", "client_file_id"],
        )


def downgrade():
    with op.batch_alter_table("upload_batch_items") as batch:
        batch.drop_constraint("uq_upload_batch_items_selection_client_file", type_="unique")
        batch.drop_index("ix_upload_batch_items_selection_session_id")
        batch.drop_constraint("fk_upload_batch_items_selection_session", type_="foreignkey")
        batch.drop_column("selection_session_id")
