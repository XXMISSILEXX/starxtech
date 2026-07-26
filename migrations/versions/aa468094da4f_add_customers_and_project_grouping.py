"""add customers and project grouping

Revision ID: aa468094da4f
Revises: 20260725_0026
Create Date: 2026-07-26
"""
from alembic import op
import sqlalchemy as sa


revision = "aa468094da4f"
down_revision = "20260725_0026"
branch_labels = None
depends_on = None

ID_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
UNCLASSIFIED_NAME = "Khách hàng chưa phân loại"
UNCLASSIFIED_NORMALIZED_NAME = "khách hàng chưa phân loại"


def upgrade():
    op.create_table(
        "customers",
        sa.Column("id", ID_TYPE, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_by_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_customers_is_active", "customers", ["is_active"])
    op.create_index("ix_customers_normalized_name", "customers", ["normalized_name"])
    op.create_index(
        "uq_customers_active_normalized_name",
        "customers",
        ["normalized_name"],
        unique=True,
        postgresql_where=sa.text("is_active"),
        sqlite_where=sa.text("is_active"),
    )

    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("customer_id", sa.BigInteger(), nullable=True))
        batch.create_index("ix_projects_customer_id", ["customer_id"])
        batch.create_foreign_key("fk_projects_customer_id_customers", "customers", ["customer_id"], ["id"], ondelete="RESTRICT")

    bind = op.get_bind()
    customers = sa.table(
        "customers",
        sa.column("id", ID_TYPE),
        sa.column("name", sa.String()),
        sa.column("normalized_name", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    projects = sa.table("projects", sa.column("customer_id", sa.BigInteger()))
    customer_id = bind.execute(
        sa.select(customers.c.id).where(customers.c.normalized_name == UNCLASSIFIED_NORMALIZED_NAME)
    ).scalar()
    if customer_id is None:
        bind.execute(
            customers.insert().values(
                name=UNCLASSIFIED_NAME,
                normalized_name=UNCLASSIFIED_NORMALIZED_NAME,
                is_active=True,
            )
        )
        customer_id = bind.execute(
            sa.select(customers.c.id).where(customers.c.normalized_name == UNCLASSIFIED_NORMALIZED_NAME)
        ).scalar_one()
    bind.execute(
        projects.update().where(projects.c.customer_id.is_(None)).values(customer_id=customer_id)
    )


def downgrade():
    with op.batch_alter_table("projects") as batch:
        batch.drop_constraint("fk_projects_customer_id_customers", type_="foreignkey")
        batch.drop_index("ix_projects_customer_id")
        batch.drop_column("customer_id")
    op.drop_index("uq_customers_active_normalized_name", table_name="customers")
    op.drop_index("ix_customers_normalized_name", table_name="customers")
    op.drop_index("ix_customers_is_active", table_name="customers")
    op.drop_table("customers")
