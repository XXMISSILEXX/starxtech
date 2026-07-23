"""add storage dashboard aggregate indexes

Revision ID: 20260723_0019
Revises: 20260722_0018
"""
from alembic import op

revision = "20260723_0019"
down_revision = "20260722_0018"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("idx_download_events_created", "download_events", ["created_at"])
    op.create_index("idx_download_events_module_created", "download_events", ["module", "created_at"])
    op.create_index("idx_download_events_source_type_created", "download_events", ["source_type", "created_at"])
    op.create_index("idx_download_events_object_created", "download_events", ["storage_object_id", "created_at"])
    op.create_index("idx_storage_objects_created", "storage_objects", ["created_at"])


def downgrade():
    op.drop_index("idx_storage_objects_created", table_name="storage_objects")
    op.drop_index("idx_download_events_object_created", table_name="download_events")
    op.drop_index("idx_download_events_source_type_created", table_name="download_events")
    op.drop_index("idx_download_events_module_created", table_name="download_events")
    op.drop_index("idx_download_events_created", table_name="download_events")
