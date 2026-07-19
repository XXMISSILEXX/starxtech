"""add partner management module

Revision ID: 20260708_0003
Revises: 20260708_0002
Create Date: 2026-07-08
"""

from alembic import op
import sqlalchemy as sa


revision = "20260708_0003"
down_revision = "20260708_0002"
branch_labels = None
depends_on = None


NEW_ROLES = "'SUPER_ADMIN', 'ADMIN', 'VIEWER_ADMIN', 'PROJECT_MANAGER', 'REPORTER'"
OLD_ROLES = "'SUPER_ADMIN', 'VIEWER_ADMIN', 'PROJECT_MANAGER', 'REPORTER'"


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("ck_users_role", type_="check")
        batch_op.create_check_constraint("ck_users_role", f"role IN ({NEW_ROLES})")

    op.create_table(
        "companies",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("industry", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=100), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_companies_name"), "companies", ["name"], unique=False)

    op.create_table(
        "partner_field_definitions",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("field_key", sa.String(length=120), nullable=False),
        sa.Column("field_type", sa.String(length=50), nullable=False),
        sa.Column("group_name", sa.String(length=255), nullable=True),
        sa.Column("options_json", sa.JSON(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_required", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("field_key"),
    )

    op.create_table(
        "partners",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=True),
        sa.Column("department", sa.String(length=255), nullable=True),
        sa.Column("position", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=100), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("updated_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_partners_company_id"), "partners", ["company_id"], unique=False)
    op.create_index(op.f("ix_partners_full_name"), "partners", ["full_name"], unique=False)

    op.create_table(
        "partner_field_values",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("partner_id", sa.BigInteger(), nullable=False),
        sa.Column("field_definition_id", sa.BigInteger(), nullable=True),
        sa.Column("field_label_snapshot", sa.String(length=255), nullable=False),
        sa.Column("field_key_snapshot", sa.String(length=120), nullable=True),
        sa.Column("field_type_snapshot", sa.String(length=50), nullable=False),
        sa.Column("group_name_snapshot", sa.String(length=255), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("value_number", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("value_date", sa.Date(), nullable=True),
        sa.Column("value_boolean", sa.Boolean(), nullable=True),
        sa.Column("value_json", sa.JSON(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["field_definition_id"], ["partner_field_definitions.id"]),
        sa.ForeignKeyConstraint(["partner_id"], ["partners.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_partner_field_values_partner_id",
        "partner_field_values",
        ["partner_id"],
        unique=False,
    )

    op.create_table(
        "partner_relationships",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("from_partner_id", sa.BigInteger(), nullable=False),
        sa.Column("to_partner_id", sa.BigInteger(), nullable=False),
        sa.Column("relationship_type", sa.String(length=120), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["from_partner_id"], ["partners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_partner_id"], ["partners.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_partner_relationships_from_partner_id"),
        "partner_relationships",
        ["from_partner_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_partner_relationships_to_partner_id"),
        "partner_relationships",
        ["to_partner_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_partner_relationships_to_partner_id"), table_name="partner_relationships")
    op.drop_index(op.f("ix_partner_relationships_from_partner_id"), table_name="partner_relationships")
    op.drop_table("partner_relationships")
    op.drop_index("idx_partner_field_values_partner_id", table_name="partner_field_values")
    op.drop_table("partner_field_values")
    op.drop_index(op.f("ix_partners_full_name"), table_name="partners")
    op.drop_index(op.f("ix_partners_company_id"), table_name="partners")
    op.drop_table("partners")
    op.drop_table("partner_field_definitions")
    op.drop_index(op.f("ix_companies_name"), table_name="companies")
    op.drop_table("companies")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("ck_users_role", type_="check")
        batch_op.create_check_constraint("ck_users_role", f"role IN ({OLD_ROLES})")
