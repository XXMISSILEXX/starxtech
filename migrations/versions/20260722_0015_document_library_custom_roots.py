"""allow project document custom roots

Revision ID: 20260722_0015
Revises: 20260722_0014
"""
from alembic import op
import sqlalchemy as sa

revision = "20260722_0015"
down_revision = "20260722_0014"
branch_labels = None
depends_on = None

def upgrade():
    # Alembic's SQLite batch reflection cannot introspect this expression index.
    # Drop/recreate it explicitly around the table copy instead of suppressing
    # the warning (PostgreSQL keeps the same invariant).
    op.execute("DROP INDEX IF EXISTS uq_project_document_folders_sibling_name")
    with op.batch_alter_table("project_document_folders") as batch:
        batch.add_column(sa.Column("root_type", sa.String(20), nullable=False, server_default="project"))
        batch.alter_column("project_id", existing_type=sa.BigInteger(), nullable=True)
    with op.batch_alter_table("project_document_files") as batch:
        batch.alter_column("project_id", existing_type=sa.BigInteger(), nullable=True)
    op.execute("UPDATE project_document_folders SET root_type='project' WHERE root_type IS NULL")
    op.execute("CREATE UNIQUE INDEX uq_project_document_folders_sibling_name ON project_document_folders (project_id, parent_id, lower(name)) WHERE deleted_at IS NULL AND is_active")

def downgrade():
    with op.batch_alter_table("project_document_files") as batch:
        batch.alter_column("project_id", existing_type=sa.BigInteger(), nullable=False)
    op.execute("DROP INDEX IF EXISTS uq_project_document_folders_sibling_name")
    with op.batch_alter_table("project_document_folders") as batch:
        batch.alter_column("project_id", existing_type=sa.BigInteger(), nullable=False)
        batch.drop_column("root_type")
    op.execute("CREATE UNIQUE INDEX uq_project_document_folders_sibling_name ON project_document_folders (project_id, parent_id, lower(name)) WHERE deleted_at IS NULL AND is_active")
