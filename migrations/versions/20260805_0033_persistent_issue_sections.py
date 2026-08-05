"""add persistent issue sections

Revision ID: 20260805_0033
Revises: 20260804_0032
"""

from alembic import op
import sqlalchemy as sa


revision = "20260805_0033"
down_revision = "20260804_0032"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "persistent_issue_sections",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("persistent_issue_id", sa.BigInteger(), nullable=False),
        sa.Column("report_category_id", sa.BigInteger(), nullable=False),
        sa.Column("severity", sa.String(length=50), server_default="MEDIUM", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="OPEN", nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("owner_user_id", sa.BigInteger(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("proposed_solution", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_by_id", sa.BigInteger(), nullable=False),
        sa.Column("updated_by_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_persistent_issue_sections_severity",
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'PROCESSING', 'RESOLVED', 'CLOSED')",
            name="ck_persistent_issue_sections_status",
        ),
        sa.ForeignKeyConstraint(["persistent_issue_id"], ["persistent_issues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_category_id"], ["report_categories.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "persistent_issue_id",
            "report_category_id",
            name="uq_persistent_issue_sections_issue_category",
        ),
    )
    op.create_index(
        "idx_persistent_issue_sections_persistent_issue_id",
        "persistent_issue_sections",
        ["persistent_issue_id"],
        unique=False,
    )
    op.create_index(
        "idx_persistent_issue_sections_report_category_id",
        "persistent_issue_sections",
        ["report_category_id"],
        unique=False,
    )

    bind = op.get_bind()
    issues = bind.execute(
        sa.text(
            "SELECT id, project_id, severity, status, due_date, owner_user_id, "
            "created_by_user_id, deleted_at FROM persistent_issues ORDER BY id"
        )
    ).mappings()

    sections = sa.table(
        "persistent_issue_sections",
        sa.column("persistent_issue_id", sa.BigInteger()),
        sa.column("report_category_id", sa.BigInteger()),
        sa.column("severity", sa.String()),
        sa.column("status", sa.String()),
        sa.column("due_date", sa.Date()),
        sa.column("owner_user_id", sa.BigInteger()),
        sa.column("description", sa.Text()),
        sa.column("proposed_solution", sa.Text()),
        sa.column("sort_order", sa.Integer()),
        sa.column("created_by_id", sa.BigInteger()),
        sa.column("deleted_at", sa.DateTime()),
    )

    for issue in issues:
        category_id = bind.execute(
            sa.text(
                "SELECT id FROM report_categories "
                "WHERE project_id = :project_id AND is_active = true "
                "ORDER BY sort_order, id LIMIT 1"
            ),
            {"project_id": issue["project_id"]},
        ).scalar_one_or_none()
        if category_id is None:
            raise RuntimeError(
                "Cannot migrate persistent issue sections: project "
                f"{issue['project_id']} for persistent issue {issue['id']} has no active report category."
            )

        bind.execute(
            sections.insert().values(
                persistent_issue_id=issue["id"],
                report_category_id=category_id,
                severity=issue["severity"],
                status=issue["status"],
                due_date=issue["due_date"],
                owner_user_id=issue["owner_user_id"],
                description=None,
                proposed_solution=None,
                sort_order=0,
                created_by_id=issue["created_by_user_id"],
                deleted_at=issue["deleted_at"],
            )
        )


def downgrade():
    op.drop_table("persistent_issue_sections")
