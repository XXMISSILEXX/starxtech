"""add daily report create idempotency key

Revision ID: 20260725_0026
Revises: 20260724_0025
"""
from alembic import op
import sqlalchemy as sa

revision = "20260725_0026"
down_revision = "20260724_0025"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("daily_reports") as batch:
        batch.add_column(sa.Column("client_request_id", sa.String(length=36), nullable=True))
        batch.create_unique_constraint(
            "uq_daily_reports_project_client_request",
            ["project_id", "client_request_id"],
        )


def downgrade():
    with op.batch_alter_table("daily_reports") as batch:
        batch.drop_constraint("uq_daily_reports_project_client_request", type_="unique")
        batch.drop_column("client_request_id")
