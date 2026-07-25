"""remove Daily Reports soft-delete lifecycle

Revision ID: 20260724_0023
Revises: 20260723_0022
"""
from alembic import op
import sqlalchemy as sa


revision = "20260724_0023"
down_revision = "20260723_0022"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    deleted_count = bind.execute(sa.text(
        "SELECT COUNT(*) FROM daily_reports WHERE deleted_at IS NOT NULL"
    )).scalar_one()
    if deleted_count:
        raise RuntimeError(
            "Có DailyReport soft-delete. Chạy flask dev-purge-deleted-reports --apply "
            '--confirm "PURGE DELETED REPORTS" trước khi upgrade 20260724_0023.'
        )
    with op.batch_alter_table("daily_reports") as batch:
        batch.drop_column("deleted_at")


def downgrade():
    with op.batch_alter_table("daily_reports") as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
