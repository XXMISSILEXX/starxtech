"""add ZIP stream download event fields

Revision ID: 20260722_0018
Revises: 20260722_0017
"""
from alembic import op
import sqlalchemy as sa

revision = "20260722_0018"
down_revision = "20260722_0017"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("download_events") as batch:
        batch.add_column(sa.Column("source_type", sa.String(30), nullable=True))
        batch.add_column(sa.Column("module", sa.String(40), nullable=True))
        batch.add_column(sa.Column("estimated_storage_egress_bytes", sa.BigInteger(), nullable=True))
        batch.add_column(sa.Column("estimated_client_egress_bytes", sa.BigInteger(), nullable=True))

def downgrade():
    with op.batch_alter_table("download_events") as batch:
        batch.drop_column("estimated_client_egress_bytes")
        batch.drop_column("estimated_storage_egress_bytes")
        batch.drop_column("module")
        batch.drop_column("source_type")
