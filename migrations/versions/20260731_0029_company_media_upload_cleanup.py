"""add Company Media upload cleanup timestamp

Revision ID: 20260731_0029
Revises: 20260730_0028
"""

from alembic import op
import sqlalchemy as sa


revision = "20260731_0029"
down_revision = "20260730_0028"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("upload_selection_sessions") as batch:
        batch.add_column(sa.Column("cleaned_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("upload_selection_sessions") as batch:
        batch.drop_column("cleaned_at")
