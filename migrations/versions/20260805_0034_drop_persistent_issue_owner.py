"""drop persistent issue owner

Revision ID: 20260805_0034
Revises: 20260805_0033

The downgrade recreates ``persistent_issues.owner_user_id`` from the section
with the smallest ``sort_order`` (then smallest ``id``) for each issue.  This
is intentionally a lossy reverse mapping when an issue has multiple sections.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260805_0034"
down_revision = "20260805_0033"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("persistent_issues", "owner_user_id")


def downgrade():
    op.add_column(
        "persistent_issues",
        sa.Column("owner_user_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_persistent_issues_owner_user_id_users",
        "persistent_issues",
        "users",
        ["owner_user_id"],
        ["id"],
    )
    op.get_bind().execute(
        sa.text(
            """
            UPDATE persistent_issues AS issue
            SET owner_user_id = (
                SELECT section.owner_user_id
                FROM persistent_issue_sections AS section
                WHERE section.persistent_issue_id = issue.id
                ORDER BY section.sort_order, section.id
                LIMIT 1
            )
            """
        )
    )
