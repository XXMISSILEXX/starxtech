"""add project update timeline

Revision ID: c4d2e980f617
Revises: b9f1c210e8d4
"""
from alembic import op
import sqlalchemy as sa

revision = "c4d2e980f617"
down_revision = "b9f1c210e8d4"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("project_updates", sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True), sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False), sa.Column("contractor_assignment_id", sa.BigInteger(), sa.ForeignKey("project_contractor_assignments.id", ondelete="RESTRICT")), sa.Column("update_type", sa.String(30), nullable=False, server_default="GENERAL"), sa.Column("title", sa.String(255), nullable=False), sa.Column("content", sa.Text(), nullable=False), sa.Column("update_date", sa.Date(), nullable=False), sa.Column("created_by_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False), sa.Column("updated_by_id", sa.BigInteger(), sa.ForeignKey("users.id")), sa.Column("deleted_at", sa.DateTime()), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")), sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")), sa.CheckConstraint("update_type IN ('GENERAL', 'PROGRESS', 'HANDOVER', 'CONTRACTOR', 'STATUS_CHANGE', 'NOTE')", name="ck_project_updates_type"))
    for name, columns in (("ix_project_updates_project_id", ["project_id"]), ("ix_project_updates_assignment_id", ["contractor_assignment_id"]), ("ix_project_updates_update_date", ["update_date"]), ("ix_project_updates_deleted_at", ["deleted_at"]), ("ix_project_updates_project_date", ["project_id", "update_date"]), ("ix_project_updates_assignment_date", ["contractor_assignment_id", "update_date"])): op.create_index(name, "project_updates", columns)

def downgrade():
    op.drop_table("project_updates")
