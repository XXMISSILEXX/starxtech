from app.models import AuditLog


def test_audit_log_indexes_are_declared_in_model_metadata(app):
    indexes = {
        index.name: tuple(column.name for column in index.columns)
        for index in AuditLog.__table__.indexes
    }

    assert indexes == {
        "idx_audit_logs_created_at": ("created_at",),
        "idx_audit_logs_action_created_at": ("action", "created_at"),
        "idx_audit_logs_actor_created_at": ("actor_user_id", "created_at"),
        "idx_audit_logs_entity": ("entity_type", "entity_id"),
    }
