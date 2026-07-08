"""add project manager role

Revision ID: 20260708_0002
Revises: 20260708_0001
Create Date: 2026-07-08
"""

from alembic import op


revision = "20260708_0002"
down_revision = "20260708_0001"
branch_labels = None
depends_on = None


NEW_ROLES = "'SUPER_ADMIN', 'VIEWER_ADMIN', 'PROJECT_MANAGER', 'REPORTER'"
OLD_ROLES = "'SUPER_ADMIN', 'VIEWER_ADMIN', 'REPORTER'"


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("ck_users_role", type_="check")
        batch_op.create_check_constraint("ck_users_role", f"role IN ({NEW_ROLES})")


def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("ck_users_role", type_="check")
        batch_op.create_check_constraint("ck_users_role", f"role IN ({OLD_ROLES})")
