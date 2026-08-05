"""add audit log indexes

Revision ID: 20260804_0032
Revises: 233012a8c8dc

At roughly half a million audit rows, adding these indexes must use CREATE
INDEX CONCURRENTLY outside a transaction. That requires a different migration;
this normal transactional migration is appropriate for the current small table.
"""

from alembic import op


revision = "20260804_0032"
down_revision = "233012a8c8dc"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("idx_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("idx_audit_logs_action_created_at", "audit_logs", ["action", "created_at"])
    op.create_index("idx_audit_logs_actor_created_at", "audit_logs", ["actor_user_id", "created_at"])
    op.create_index("idx_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])


def downgrade():
    op.drop_index("idx_audit_logs_entity", table_name="audit_logs")
    op.drop_index("idx_audit_logs_actor_created_at", table_name="audit_logs")
    op.drop_index("idx_audit_logs_action_created_at", table_name="audit_logs")
    op.drop_index("idx_audit_logs_created_at", table_name="audit_logs")
