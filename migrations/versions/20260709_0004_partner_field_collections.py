"""add partner field collections

Revision ID: 20260709_0004
Revises: 20260708_0003
Create Date: 2026-07-09
"""

from alembic import op
import sqlalchemy as sa


revision = "20260709_0004"
down_revision = "20260708_0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "partner_field_collections",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_partner_field_collections_name"), "partner_field_collections", ["name"], unique=False)

    op.create_table(
        "partner_field_collection_items",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("collection_id", sa.BigInteger(), nullable=False),
        sa.Column("field_definition_id", sa.BigInteger(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["collection_id"], ["partner_field_collections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["field_definition_id"], ["partner_field_definitions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("collection_id", "field_definition_id", name="uq_partner_field_collection_field"),
    )
    op.create_index(
        op.f("ix_partner_field_collection_items_collection_id"),
        "partner_field_collection_items",
        ["collection_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_partner_field_collection_items_field_definition_id"),
        "partner_field_collection_items",
        ["field_definition_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_partner_field_collection_items_field_definition_id"), table_name="partner_field_collection_items")
    op.drop_index(op.f("ix_partner_field_collection_items_collection_id"), table_name="partner_field_collection_items")
    op.drop_table("partner_field_collection_items")
    op.drop_index(op.f("ix_partner_field_collections_name"), table_name="partner_field_collections")
    op.drop_table("partner_field_collections")
