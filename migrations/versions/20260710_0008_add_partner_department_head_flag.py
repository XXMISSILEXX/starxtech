"""add partner department head flag

Revision ID: 20260710_0008
Revises: 20260709_0007
Create Date: 2026-07-10
"""

from alembic import op
import sqlalchemy as sa


revision = "20260710_0008"
down_revision = "20260709_0007"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("partners") as batch_op:
        batch_op.add_column(sa.Column("is_department_head", sa.Boolean(), server_default="false", nullable=False))

    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        """
        UPDATE partners
        SET is_department_head = true
        WHERE EXISTS (
            SELECT 1
            FROM partner_relationships
            JOIN company_departments
              ON company_departments.id = partner_relationships.department_id
            WHERE partner_relationships.partner_id = partners.id
              AND partner_relationships.is_department_head = true
              AND partner_relationships.is_active = true
              AND partner_relationships.deleted_at IS NULL
              AND company_departments.is_special_department = false
        )
        """
    )


def downgrade():
    with op.batch_alter_table("partners") as batch_op:
        batch_op.drop_column("is_department_head")
