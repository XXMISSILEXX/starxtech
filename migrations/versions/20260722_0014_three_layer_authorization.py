"""refactor authorization to global RBAC, project memberships, and ACL

Revision ID: 20260722_0014
Revises: 20260721_0013
"""
from alembic import op
import sqlalchemy as sa

revision = "20260722_0014"
down_revision = "20260721_0013"
branch_labels = None
depends_on = None

FLAGS = (
    "can_view_project", "can_view_reports", "can_create_reports", "can_edit_own_reports",
    "can_edit_all_reports", "can_archive_reports", "can_view_issues", "can_create_issues",
    "can_edit_issues", "can_close_reopen_issues", "can_manage_report_categories",
    "can_view_documents", "can_upload_documents", "can_edit_documents", "can_share_documents",
    "can_archive_documents", "can_restore_documents",
)


def upgrade():
    bind = op.get_bind()
    # The compatibility mirror must accept custom role codes.
    with op.batch_alter_table("users") as batch:
        try:
            batch.drop_constraint("ck_users_role", type_="check")
        except ValueError:
            pass
        batch.alter_column("role", existing_type=sa.String(50), nullable=True)

    # SQLite batch mode rebuilds the table.  Rename first, then open a second
    # batch for the new column name; referring to it in the same batch causes
    # Alembic's column lookup to raise KeyError on an empty fresh database.
    with op.batch_alter_table("project_users") as batch:
        batch.alter_column("role_in_project", new_column_name="project_role_code", existing_type=sa.String(50))
    with op.batch_alter_table("project_users") as batch:
        batch.alter_column("project_role_code", existing_type=sa.String(50), server_default="PROJECT_VIEWER")
        batch.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")))
        for flag in FLAGS:
            batch.add_column(sa.Column(flag, sa.Boolean(), nullable=False, server_default=sa.text("false")))
        batch.add_column(sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))

    # Existing assignments retain the old project capabilities, independently
    # of any later global role reassignment.
    manager_flags = ", ".join(f"{flag} = true" for flag in FLAGS)
    reporter_flags = ", ".join(f"{flag} = true" for flag in (
        "can_view_project", "can_view_reports", "can_create_reports", "can_edit_own_reports",
        "can_view_issues", "can_view_documents", "can_upload_documents",
    ))
    bind.execute(sa.text("UPDATE project_users SET project_role_code='PROJECT_OWNER', " + manager_flags + " WHERE project_role_code IN ('PROJECT_MANAGER', 'MEMBER') AND user_id IN (SELECT id FROM users WHERE role='PROJECT_MANAGER')"))
    bind.execute(sa.text("UPDATE project_users SET project_role_code='PROJECT_REPORTER', " + reporter_flags + " WHERE user_id IN (SELECT id FROM users WHERE role='REPORTER')"))

    role = bind.execute(sa.text("SELECT id FROM roles WHERE code='PROJECT_STAFF'")).scalar()
    if role is None:
        bind.execute(sa.text("INSERT INTO roles (code, name, description, is_system, created_at, updated_at) VALUES ('PROJECT_STAFF', 'Nhân sự dự án', 'Vai trò tương thích; quyền dự án nằm ở membership.', false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
        role = bind.execute(sa.text("SELECT id FROM roles WHERE code='PROJECT_STAFF'")).scalar()
    bind.execute(sa.text("UPDATE users SET role_id=:role_id, role='PROJECT_STAFF' WHERE role IN ('PROJECT_MANAGER','REPORTER')"), {"role_id": role})
    bind.execute(sa.text("UPDATE roles SET is_system=false, name='[Deprecated] ' || name WHERE code IN ('PROJECT_MANAGER','REPORTER')"))


def downgrade():
    with op.batch_alter_table("project_users") as batch:
        batch.drop_column("updated_at")
        for flag in reversed(FLAGS):
            batch.drop_column(flag)
        batch.drop_column("is_active")
        batch.alter_column("project_role_code", new_column_name="role_in_project", existing_type=sa.String(50))
    with op.batch_alter_table("users") as batch:
        batch.alter_column("role", existing_type=sa.String(50), nullable=False)
        batch.create_check_constraint("ck_users_role", "role IN ('SUPER_ADMIN', 'ADMIN', 'VIEWER_ADMIN', 'PROJECT_MANAGER', 'REPORTER')")
