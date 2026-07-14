"""improve partner relationship tree

Revision ID: 20260709_0005
Revises: 20260709_0004
Create Date: 2026-07-09
"""

from alembic import op
import sqlalchemy as sa


revision = "20260709_0005"
down_revision = "20260709_0004"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("partner_relationships") as batch_op:
        batch_op.add_column(sa.Column("company_id", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("partner_id", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("department", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("position_title", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("parent_partner_id", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("parent_relationship_id", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("is_department_head", sa.Boolean(), server_default="false", nullable=False))
        batch_op.add_column(sa.Column("display_order", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("note", sa.Text(), nullable=True))
        batch_op.create_foreign_key("fk_partner_relationships_company_id", "companies", ["company_id"], ["id"])
        batch_op.create_foreign_key("fk_partner_relationships_partner_id", "partners", ["partner_id"], ["id"], ondelete="CASCADE")
        batch_op.create_foreign_key(
            "fk_partner_relationships_parent_partner_id",
            "partners",
            ["parent_partner_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_partner_relationships_parent_relationship_id",
            "partner_relationships",
            ["parent_relationship_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_partner_relationships_company_id", ["company_id"])
        batch_op.create_index("ix_partner_relationships_partner_id", ["partner_id"])
        batch_op.create_index("ix_partner_relationships_parent_partner_id", ["parent_partner_id"])

    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        """
        UPDATE partner_relationships
        SET
            partner_id = to_partner_id,
            parent_partner_id = from_partner_id,
            company_id = (SELECT company_id FROM partners WHERE partners.id = partner_relationships.to_partner_id),
            department = (SELECT department FROM partners WHERE partners.id = partner_relationships.to_partner_id),
            position_title = (SELECT position FROM partners WHERE partners.id = partner_relationships.to_partner_id),
            note = notes
        WHERE partner_id IS NULL
        """
    )


def downgrade():
    with op.batch_alter_table("partner_relationships") as batch_op:
        batch_op.drop_index("ix_partner_relationships_parent_partner_id")
        batch_op.drop_index("ix_partner_relationships_partner_id")
        batch_op.drop_index("ix_partner_relationships_company_id")
        batch_op.drop_constraint("fk_partner_relationships_parent_relationship_id", type_="foreignkey")
        batch_op.drop_constraint("fk_partner_relationships_parent_partner_id", type_="foreignkey")
        batch_op.drop_constraint("fk_partner_relationships_partner_id", type_="foreignkey")
        batch_op.drop_constraint("fk_partner_relationships_company_id", type_="foreignkey")
        batch_op.drop_column("note")
        batch_op.drop_column("display_order")
        batch_op.drop_column("is_department_head")
        batch_op.drop_column("parent_relationship_id")
        batch_op.drop_column("parent_partner_id")
        batch_op.drop_column("position_title")
        batch_op.drop_column("department")
        batch_op.drop_column("partner_id")
        batch_op.drop_column("company_id")
