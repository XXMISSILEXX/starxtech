"""add progress item decimal places

Revision ID: 20260802_0030
Revises: 6c53d69bfb07
Create Date: 2026-08-02
"""

from alembic import op
import sqlalchemy as sa


revision = "20260802_0030"
down_revision = "6c53d69bfb07"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("progress_items") as batch:
        batch.add_column(sa.Column("decimal_places", sa.SmallInteger(), nullable=False, server_default="0"))
        batch.create_check_constraint("ck_progress_items_decimal_places_range", "decimal_places BETWEEN 0 AND 3")


def downgrade():
    with op.batch_alter_table("progress_items") as batch:
        batch.drop_constraint("ck_progress_items_decimal_places_range", type_="check")
        batch.drop_column("decimal_places")
