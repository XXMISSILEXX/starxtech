from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

from app.extensions import db
from app.models.mixins import CreatedAtMixin


class AuditLog(CreatedAtMixin, db.Model):
    __tablename__ = "audit_logs"
    __table_args__ = (
        db.Index("idx_audit_logs_created_at", "created_at"),
        db.Index("idx_audit_logs_action_created_at", "action", "created_at"),
        db.Index("idx_audit_logs_actor_created_at", "actor_user_id", "created_at"),
        db.Index("idx_audit_logs_entity", "entity_type", "entity_id"),
    )

    id = db.Column(db.BigInteger, primary_key=True)
    actor_user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(100), nullable=False)
    entity_id = db.Column(db.BigInteger, nullable=True)
    old_values_json = db.Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    new_values_json = db.Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    ip_address = db.Column(db.String(100), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)

    actor = db.relationship(
        "User",
        back_populates="audit_logs",
        foreign_keys=[actor_user_id],
    )
