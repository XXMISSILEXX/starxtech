"""add project documents core

Revision ID: 20260720_0012
Revises: 20260720_0011
"""
from alembic import op
import sqlalchemy as sa

revision = "20260720_0012"
down_revision = "20260720_0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "project_document_folders",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", sa.BigInteger(), sa.ForeignKey("project_document_folders.id", ondelete="RESTRICT")),
        sa.Column("name", sa.String(255), nullable=False), sa.Column("description", sa.Text()),
        sa.Column("is_root", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_restricted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_by_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")), sa.Column("deleted_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_project_document_folders_parent", "project_document_folders", ["project_id", "parent_id", "deleted_at"])
    op.create_index("idx_project_document_folders_root", "project_document_folders", ["project_id", "is_root"])
    op.execute("CREATE UNIQUE INDEX uq_project_document_folders_root ON project_document_folders (project_id) WHERE is_root AND deleted_at IS NULL")
    op.execute("CREATE UNIQUE INDEX uq_project_document_folders_sibling_name ON project_document_folders (project_id, parent_id, lower(name)) WHERE deleted_at IS NULL AND is_active")
    op.create_table(
        "project_document_files",
        sa.Column("id", sa.BigInteger(), primary_key=True), sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("folder_id", sa.BigInteger(), sa.ForeignKey("project_document_folders.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("storage_object_id", sa.BigInteger(), sa.ForeignKey("storage_objects.id"), nullable=False), sa.Column("display_name", sa.String(255), nullable=False), sa.Column("description", sa.Text()), sa.Column("tags", sa.JSON()),
        sa.Column("created_by_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False), sa.Column("updated_by_id", sa.BigInteger(), sa.ForeignKey("users.id")), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")), sa.Column("deleted_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")), sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("storage_object_id", name="uq_project_document_files_storage_object"),
    )
    op.create_index("idx_project_document_files_folder", "project_document_files", ["project_id", "folder_id", "deleted_at"])
    op.create_table(
        "project_document_folder_permissions",
        sa.Column("id", sa.BigInteger(), primary_key=True), sa.Column("folder_id", sa.BigInteger(), sa.ForeignKey("project_document_folders.id", ondelete="CASCADE"), nullable=False), sa.Column("principal_type", sa.String(10), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE")), sa.Column("role_id", sa.BigInteger(), sa.ForeignKey("roles.id", ondelete="CASCADE")),
        sa.Column("can_view", sa.Boolean(), nullable=False, server_default=sa.text("false")), sa.Column("can_upload", sa.Boolean(), nullable=False, server_default=sa.text("false")), sa.Column("can_edit", sa.Boolean(), nullable=False, server_default=sa.text("false")), sa.Column("can_delete", sa.Boolean(), nullable=False, server_default=sa.text("false")), sa.Column("can_share", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_by_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")), sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("principal_type IN ('user', 'role')", name="ck_project_document_folder_permissions_principal"), sa.CheckConstraint("(user_id IS NOT NULL AND role_id IS NULL) OR (user_id IS NULL AND role_id IS NOT NULL)", name="ck_project_document_folder_permissions_principal_xor"), sa.UniqueConstraint("folder_id", "user_id", name="uq_project_document_folder_permissions_user"), sa.UniqueConstraint("folder_id", "role_id", name="uq_project_document_folder_permissions_role"),
    )


def downgrade():
    op.drop_table("project_document_folder_permissions")
    op.drop_table("project_document_files")
    op.execute("DROP INDEX IF EXISTS uq_project_document_folders_sibling_name")
    op.execute("DROP INDEX IF EXISTS uq_project_document_folders_root")
    op.drop_table("project_document_folders")
