from app.extensions import db
from app.models.mixins import TimestampMixin


class Customer(TimestampMixin, db.Model):
    __tablename__ = "customers"
    __table_args__ = (
        db.Index(
            "uq_customers_active_normalized_name",
            "normalized_name",
            unique=True,
            postgresql_where=db.text("is_active"),
            sqlite_where=db.text("is_active"),
        ),
        db.Index("ix_customers_is_active", "is_active"),
        db.Index("ix_customers_normalized_name", "normalized_name"),
    )

    id = db.Column(db.BigInteger().with_variant(db.Integer(), "sqlite"), primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    normalized_name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    archived_at = db.Column(db.DateTime, nullable=True)
    created_by_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)
    updated_by_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)

    created_by = db.relationship("User", foreign_keys=[created_by_id])
    updated_by = db.relationship("User", foreign_keys=[updated_by_id])
    projects = db.relationship("Project", back_populates="customer")
