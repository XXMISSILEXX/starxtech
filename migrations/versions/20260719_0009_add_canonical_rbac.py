"""add canonical RBAC tables while preserving users.role

Revision ID: 20260719_0009
Revises: 20260710_0008
"""
from alembic import op
import sqlalchemy as sa

revision = "20260719_0009"
down_revision = "20260710_0008"
branch_labels = None
depends_on = None

ROLE_NAMES = {
    "SUPER_ADMIN": "Quản trị tổng", "ADMIN": "Quản trị viên", "VIEWER_ADMIN": "Quản trị viên chỉ xem",
    "PROJECT_MANAGER": "Quản lý dự án", "REPORTER": "Người báo cáo",
}
ID_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")

def upgrade():
    op.create_table("roles", sa.Column("id", ID_TYPE, primary_key=True, autoincrement=True), sa.Column("code", sa.String(50), nullable=False),
                    sa.Column("name", sa.String(255), nullable=False), sa.Column("description", sa.Text()),
                    sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("true")),
                    sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")), sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
                    sa.UniqueConstraint("code", name="uq_roles_code"))
    op.create_index("ix_roles_code", "roles", ["code"])
    op.create_table("permissions", sa.Column("id", ID_TYPE, primary_key=True, autoincrement=True), sa.Column("code", sa.String(100), nullable=False),
                    sa.Column("name", sa.String(255), nullable=False), sa.Column("description", sa.Text()), sa.Column("module", sa.String(100), nullable=False),
                    sa.Column("group_name", sa.String(100), nullable=False), sa.Column("action", sa.String(50), nullable=False), sa.Column("resource", sa.String(100), nullable=False),
                    sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"), sa.Column("is_dangerous", sa.Boolean(), nullable=False, server_default=sa.text("false")), sa.Column("is_deprecated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
                    sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")), sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")), sa.UniqueConstraint("code", name="uq_permissions_code"))
    op.create_index("ix_permissions_code", "permissions", ["code"])
    op.create_table("role_permissions", sa.Column("id", ID_TYPE, primary_key=True, autoincrement=True), sa.Column("role_id", ID_TYPE, nullable=False), sa.Column("permission_id", ID_TYPE, nullable=False),
                    sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"), sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permissions_role_permission"))
    op.create_index("ix_role_permissions_role_id", "role_permissions", ["role_id"])
    op.create_index("ix_role_permissions_permission_id", "role_permissions", ["permission_id"])
    bind = op.get_bind()
    roles = [{"code": code, "name": name, "is_system": True} for code, name in ROLE_NAMES.items()]
    bind.execute(sa.table("roles", sa.column("code"), sa.column("name"), sa.column("is_system")).insert(), roles)
    invalid = bind.execute(sa.text("SELECT DISTINCT role FROM users WHERE role NOT IN ('SUPER_ADMIN','ADMIN','VIEWER_ADMIN','PROJECT_MANAGER','REPORTER') OR role IS NULL")).fetchall()
    if invalid:
        values = ", ".join(repr(row[0]) for row in invalid)
        raise RuntimeError("Cannot migrate RBAC: invalid users.role values: " + values)
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("role_id", ID_TYPE, nullable=True))
    bind.execute(sa.text("UPDATE users SET role_id = roles.id FROM roles WHERE users.role = roles.code") if bind.dialect.name == "postgresql" else sa.text("UPDATE users SET role_id = (SELECT id FROM roles WHERE roles.code = users.role)"))
    with op.batch_alter_table("users") as batch:
        batch.create_foreign_key("fk_users_role_id_roles", "roles", ["role_id"], ["id"])
        batch.create_index("ix_users_role_id", ["role_id"])
        batch.alter_column("role_id", nullable=False)

def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_role_id")
        batch.drop_constraint("fk_users_role_id_roles", type_="foreignkey")
        batch.drop_column("role_id")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")
