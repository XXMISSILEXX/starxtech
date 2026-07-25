"""add S3 references for partner photos and report attachments

Revision ID: 20260723_0020
Revises: 20260723_0019
"""
from alembic import op
import sqlalchemy as sa

revision = "20260723_0020"
down_revision = "20260723_0019"
branch_labels = None
depends_on = None


def upgrade():
    # batch_alter_table keeps this migration executable in local SQLite while
    # emitting ordinary ALTER statements on PostgreSQL.
    with op.batch_alter_table("partners") as batch:
        batch.add_column(sa.Column("profile_photo_storage_object_id", sa.BigInteger(), nullable=True))
        batch.create_foreign_key("fk_partners_profile_photo_storage_object", "storage_objects", ["profile_photo_storage_object_id"], ["id"])
        batch.create_index("idx_partners_profile_photo_storage_object", ["profile_photo_storage_object_id"])
    with op.batch_alter_table("companies") as batch:
        batch.add_column(sa.Column("company_photo_storage_object_id", sa.BigInteger(), nullable=True))
        batch.create_foreign_key("fk_companies_company_photo_storage_object", "storage_objects", ["company_photo_storage_object_id"], ["id"])
        batch.create_index("idx_companies_company_photo_storage_object", ["company_photo_storage_object_id"])
    with op.batch_alter_table("report_attachments") as batch:
        batch.add_column(sa.Column("storage_object_id", sa.BigInteger(), nullable=True))
        batch.create_foreign_key("fk_report_attachments_storage_object", "storage_objects", ["storage_object_id"], ["id"])
        batch.create_index("idx_report_attachments_storage_object", ["storage_object_id"])


def downgrade():
    with op.batch_alter_table("report_attachments") as batch:
        batch.drop_index("idx_report_attachments_storage_object")
        batch.drop_constraint("fk_report_attachments_storage_object", type_="foreignkey")
        batch.drop_column("storage_object_id")
    with op.batch_alter_table("companies") as batch:
        batch.drop_index("idx_companies_company_photo_storage_object")
        batch.drop_constraint("fk_companies_company_photo_storage_object", type_="foreignkey")
        batch.drop_column("company_photo_storage_object_id")
    with op.batch_alter_table("partners") as batch:
        batch.drop_index("idx_partners_profile_photo_storage_object")
        batch.drop_constraint("fk_partners_profile_photo_storage_object", type_="foreignkey")
        batch.drop_column("profile_photo_storage_object_id")
