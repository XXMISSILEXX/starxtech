from sqlalchemy.dialects.postgresql import JSONB

from app.extensions import db
from app.models.mixins import CreatedAtMixin


class AuditLog(CreatedAtMixin, db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.BigInteger, primary_key=True)
    actor_user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(100), nullable=False)
    entity_id = db.Column(db.BigInteger, nullable=True)
    old_values_json = db.Column(JSONB, nullable=True)
    new_values_json = db.Column(JSONB, nullable=True)
    ip_address = db.Column(db.String(100), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)

    actor = db.relationship(
        "User",
        back_populates="audit_logs",
        foreign_keys=[actor_user_id],
    )
