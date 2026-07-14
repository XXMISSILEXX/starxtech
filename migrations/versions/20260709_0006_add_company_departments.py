"""add company departments

Revision ID: 20260709_0006
Revises: 20260709_0005
Create Date: 2026-07-09
"""

from alembic import op
import sqlalchemy as sa


revision = "20260709_0006"
down_revision = "20260709_0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "company_departments",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parent_department_id", sa.BigInteger(), nullable=True),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_department_id"], ["company_departments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "name", name="uq_company_departments_company_name"),
    )
    op.create_index(op.f("ix_company_departments_company_id"), "company_departments", ["company_id"], unique=False)
    op.create_index(op.f("ix_company_departments_name"), "company_departments", ["name"], unique=False)
    op.create_index(
        op.f("ix_company_departments_parent_department_id"),
        "company_departments",
        ["parent_department_id"],
        unique=False,
    )

    with op.batch_alter_table("partners") as batch_op:
        batch_op.add_column(sa.Column("department_id", sa.BigInteger(), nullable=True))
        batch_op.create_foreign_key("fk_partners_department_id", "company_departments", ["department_id"], ["id"], ondelete="SET NULL")
        batch_op.create_index("ix_partners_department_id", ["department_id"])

    with op.batch_alter_table("partner_relationships") as batch_op:
        batch_op.add_column(sa.Column("department_id", sa.BigInteger(), nullable=True))
        batch_op.create_foreign_key(
            "fk_partner_relationships_department_id",
            "company_departments",
            ["department_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_partner_relationships_department_id", ["department_id"])

    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        """
        INSERT INTO company_departments (id, company_id, name, display_order, is_active, created_at, updated_at)
        SELECT
            row_number() OVER (ORDER BY company_id, department) + COALESCE((SELECT MAX(id) FROM company_departments), 0),
            company_id,
            department,
            0,
            true,
            now(),
            now()
        FROM (
            SELECT DISTINCT company_id, department
            FROM partners
            WHERE company_id IS NOT NULL AND department IS NOT NULL AND department <> ''
        ) source
        ON CONFLICT (company_id, name) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE partners
        SET department_id = company_departments.id
        FROM company_departments
        WHERE partners.company_id = company_departments.company_id
          AND partners.department = company_departments.name
          AND partners.department_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE partner_relationships
        SET department_id = company_departments.id
        FROM company_departments
        WHERE partner_relationships.company_id = company_departments.company_id
          AND partner_relationships.department = company_departments.name
          AND partner_relationships.department_id IS NULL
        """
    )


def downgrade():
    with op.batch_alter_table("partner_relationships") as batch_op:
        batch_op.drop_index("ix_partner_relationships_department_id")
        batch_op.drop_constraint("fk_partner_relationships_department_id", type_="foreignkey")
        batch_op.drop_column("department_id")
    with op.batch_alter_table("partners") as batch_op:
        batch_op.drop_index("ix_partners_department_id")
        batch_op.drop_constraint("fk_partners_department_id", type_="foreignkey")
        batch_op.drop_column("department_id")
    op.drop_index(op.f("ix_company_departments_parent_department_id"), table_name="company_departments")
    op.drop_index(op.f("ix_company_departments_name"), table_name="company_departments")
    op.drop_index(op.f("ix_company_departments_company_id"), table_name="company_departments")
    op.drop_table("company_departments")
