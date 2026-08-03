"""add gantt dates to progress items

Revision ID: 233012a8c8dc
Revises: 20260802_0031
Create Date: 2026-08-03 11:01:54.965031
"""

from alembic import op
import sqlalchemy as sa


revision = "233012a8c8dc"
down_revision = "20260802_0031"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("progress_items") as batch:
        batch.add_column(sa.Column("planned_start_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("planned_end_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("actual_start_date", sa.Date(), nullable=True))
        batch.create_check_constraint(
            "ck_progress_items_planned_dates_paired",
            "(planned_start_date IS NULL) = (planned_end_date IS NULL)",
        )
        batch.create_check_constraint(
            "ck_progress_items_planned_date_order",
            "planned_start_date IS NULL OR planned_start_date <= planned_end_date",
        )


def downgrade():
    with op.batch_alter_table("progress_items") as batch:
        batch.drop_constraint("ck_progress_items_planned_date_order", type_="check")
        batch.drop_constraint("ck_progress_items_planned_dates_paired", type_="check")
        batch.drop_column("actual_start_date")
        batch.drop_column("planned_end_date")
        batch.drop_column("planned_start_date")
