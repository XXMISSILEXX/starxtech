"""add special department flag

Revision ID: 20260709_0007
Revises: 20260709_0006
Create Date: 2026-07-09
"""

from alembic import op
import sqlalchemy as sa


revision = "20260709_0007"
down_revision = "20260709_0006"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("company_departments") as batch_op:
        batch_op.add_column(
            sa.Column("is_special_department", sa.Boolean(), server_default="false", nullable=False)
        )


def downgrade():
    with op.batch_alter_table("company_departments") as batch_op:
        batch_op.drop_column("is_special_department")
