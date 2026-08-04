"""drop progress structure active flags

Revision ID: 20260802_0031
Revises: 20260802_0030
Create Date: 2026-08-02
"""

from alembic import op
import sqlalchemy as sa


revision = "20260802_0031"
down_revision = "20260802_0030"
branch_labels = None
depends_on = None


def upgrade():
    for table_name in ("progress_types", "progress_groups", "progress_items"):
        with op.batch_alter_table(table_name) as batch:
            batch.drop_column("is_active")


def downgrade():
    for table_name in ("progress_items", "progress_groups", "progress_types"):
        with op.batch_alter_table(table_name) as batch:
            batch.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
