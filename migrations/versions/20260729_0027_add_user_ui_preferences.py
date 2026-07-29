"""add persisted personal UI preferences

Revision ID: 20260729_0027
Revises: 20260725_0026, c4d2e980f617
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260729_0027"
# The project-update branch was already an independent production head.  This
# migration intentionally merges it before changing users, so `flask db
# upgrade` has one safe target and existing databases from either branch work.
down_revision = ("20260725_0026", "c4d2e980f617")
branch_labels = None
depends_on = None

JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
DEFAULT_PREFERENCES = '{"appearance":"system","accent":"blue"}'


def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column(
                "ui_preferences",
                JSON_TYPE,
                nullable=False,
                server_default=sa.text(f"'{DEFAULT_PREFERENCES}'"),
            )
        )


def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.drop_column("ui_preferences")
