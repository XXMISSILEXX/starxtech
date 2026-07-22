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
    with op.batch_alter_table("project_document_folders") as batch:
        batch.add_column(sa.Column("root_type", sa.String(20), nullable=False, server_default="project"))
        batch.alter_column("project_id", existing_type=sa.BigInteger(), nullable=True)
    with op.batch_alter_table("project_document_files") as batch:
        batch.alter_column("project_id", existing_type=sa.BigInteger(), nullable=True)
    op.execute("UPDATE project_document_folders SET root_type='project' WHERE root_type IS NULL")

def downgrade():
    with op.batch_alter_table("project_document_files") as batch:
        batch.alter_column("project_id", existing_type=sa.BigInteger(), nullable=False)
    with op.batch_alter_table("project_document_folders") as batch:
        batch.alter_column("project_id", existing_type=sa.BigInteger(), nullable=False)
        batch.drop_column("root_type")
