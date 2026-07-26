"""add project contractors and assignments

Revision ID: b9f1c210e8d4
Revises: aa468094da4f
Create Date: 2026-07-26
"""
from alembic import op
import sqlalchemy as sa


revision = "b9f1c210e8d4"
down_revision = "aa468094da4f"
branch_labels = None
depends_on = None

ID_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade():
    op.create_table(
        "project_contractors",
        sa.Column("id", ID_TYPE, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("short_name", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_by_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_project_contractors_is_active", "project_contractors", ["is_active"])
    op.create_index("ix_project_contractors_normalized_name", "project_contractors", ["normalized_name"])
    op.create_index(
        "uq_project_contractors_active_normalized_name", "project_contractors", ["normalized_name"], unique=True,
        postgresql_where=sa.text("is_active"), sqlite_where=sa.text("is_active"),
    )

    op.create_table(
        "project_contractor_assignments",
        sa.Column("id", ID_TYPE, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("contractor_id", sa.BigInteger(), sa.ForeignKey("project_contractors.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="CONSTRUCTION"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
        sa.Column("started_on", sa.Date(), nullable=True),
        sa.Column("ended_on", sa.Date(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_by_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("role IN ('CONSTRUCTION', 'SOLUTION')", name="ck_project_contractor_assignments_role"),
        sa.CheckConstraint("status IN ('ACTIVE', 'PAUSED', 'COMPLETED', 'ENDED')", name="ck_project_contractor_assignments_status"),
    )
    op.create_index("ix_project_contractor_assignments_project_id", "project_contractor_assignments", ["project_id"])
    op.create_index("ix_project_contractor_assignments_contractor_id", "project_contractor_assignments", ["contractor_id"])
    op.create_index("ix_project_contractor_assignments_project_role", "project_contractor_assignments", ["project_id", "role"])
    op.create_index(
        "uq_project_contractor_assignments_open_role", "project_contractor_assignments", ["project_id", "contractor_id", "role"], unique=True,
        postgresql_where=sa.text("status != 'ENDED'"), sqlite_where=sa.text("status != 'ENDED'"),
    )


def downgrade():
    op.drop_index("uq_project_contractor_assignments_open_role", table_name="project_contractor_assignments")
    op.drop_index("ix_project_contractor_assignments_project_role", table_name="project_contractor_assignments")
    op.drop_index("ix_project_contractor_assignments_contractor_id", table_name="project_contractor_assignments")
    op.drop_index("ix_project_contractor_assignments_project_id", table_name="project_contractor_assignments")
    op.drop_table("project_contractor_assignments")
    op.drop_index("uq_project_contractors_active_normalized_name", table_name="project_contractors")
    op.drop_index("ix_project_contractors_normalized_name", table_name="project_contractors")
    op.drop_index("ix_project_contractors_is_active", table_name="project_contractors")
    op.drop_table("project_contractors")
