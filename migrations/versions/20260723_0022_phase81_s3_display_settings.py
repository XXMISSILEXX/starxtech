"""add account display image and branding setting

Revision ID: 20260723_0022
Revises: 20260723_0021
"""
from alembic import op
import sqlalchemy as sa

revision = "20260723_0022"
down_revision = "20260723_0021"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("avatar_storage_object_id", sa.BigInteger(), nullable=True))
        batch.create_foreign_key("fk_users_avatar_storage_object", "storage_objects", ["avatar_storage_object_id"], ["id"])
        batch.create_index("ix_users_avatar_storage_object_id", ["avatar_storage_object_id"])
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=120), primary_key=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("brand_logo_storage_object_id", sa.BigInteger(), sa.ForeignKey("storage_objects.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade():
    op.drop_table("system_settings")
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_avatar_storage_object_id")
        batch.drop_constraint("fk_users_avatar_storage_object", type_="foreignkey")
        batch.drop_column("avatar_storage_object_id")
