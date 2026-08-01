"""phase12 construction progress

Revision ID: 6c53d69bfb07
Revises: 20260731_0029
Create Date: 2026-08-01 16:19:37.564956
"""

from alembic import op
import sqlalchemy as sa


revision = "6c53d69bfb07"
down_revision = "20260731_0029"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "progress_types",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("value_mode", sa.String(length=20), nullable=False, server_default="quantity"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("value_mode IN ('quantity', 'money')", name="ck_progress_types_value_mode"),
        sa.UniqueConstraint("project_id", "name", name="uq_progress_types_project_name"),
    )
    op.create_index("ix_progress_types_project_id", "progress_types", ["project_id"])

    op.create_table(
        "progress_groups",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("progress_type_id", sa.BigInteger(), sa.ForeignKey("progress_types.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("progress_type_id", "name", name="uq_progress_groups_type_name"),
    )
    op.create_index("ix_progress_groups_project_id", "progress_groups", ["project_id"])
    op.create_index("ix_progress_groups_progress_type_id", "progress_groups", ["progress_type_id"])

    op.create_table(
        "progress_items",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("progress_group_id", sa.BigInteger(), sa.ForeignKey("progress_groups.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("unit", sa.String(length=30), nullable=False),
        sa.Column("planned_quantity", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("opening_quantity", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("completed_quantity", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("assignee_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("planned_quantity >= 0", name="ck_progress_items_planned_quantity_nonnegative"),
        sa.CheckConstraint("opening_quantity >= 0", name="ck_progress_items_opening_quantity_nonnegative"),
        sa.UniqueConstraint("progress_group_id", "name", name="uq_progress_items_group_name"),
    )
    op.create_index("ix_progress_items_project_id", "progress_items", ["project_id"])
    op.create_index("ix_progress_items_progress_group_id", "progress_items", ["progress_group_id"])

    op.create_table(
        "progress_entries",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("progress_item_id", sa.BigInteger(), sa.ForeignKey("progress_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("quantity > 0", name="ck_progress_entries_quantity_positive"),
        sa.UniqueConstraint("progress_item_id", "report_date", name="uq_progress_entries_item_date"),
    )
    op.create_index("ix_progress_entries_project_id", "progress_entries", ["project_id"])
    op.create_index("ix_progress_entries_progress_item_id", "progress_entries", ["progress_item_id"])
    op.create_index("ix_progress_entries_project_date", "progress_entries", ["project_id", "report_date"])

    with op.batch_alter_table("project_users") as batch:
        batch.add_column(sa.Column("can_view_progress", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("can_create_progress_entries", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("can_edit_all_progress_entries", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("can_manage_progress_structure", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table("project_users") as batch:
        batch.drop_column("can_manage_progress_structure")
        batch.drop_column("can_edit_all_progress_entries")
        batch.drop_column("can_create_progress_entries")
        batch.drop_column("can_view_progress")

    op.drop_index("ix_progress_entries_project_date", table_name="progress_entries")
    op.drop_index("ix_progress_entries_progress_item_id", table_name="progress_entries")
    op.drop_index("ix_progress_entries_project_id", table_name="progress_entries")
    op.drop_table("progress_entries")
    op.drop_index("ix_progress_items_progress_group_id", table_name="progress_items")
    op.drop_index("ix_progress_items_project_id", table_name="progress_items")
    op.drop_table("progress_items")
    op.drop_index("ix_progress_groups_progress_type_id", table_name="progress_groups")
    op.drop_index("ix_progress_groups_project_id", table_name="progress_groups")
    op.drop_table("progress_groups")
    op.drop_index("ix_progress_types_project_id", table_name="progress_types")
    op.drop_table("progress_types")
