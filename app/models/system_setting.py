from app.extensions import db
from app.models.mixins import TimestampMixin


class SystemSetting(TimestampMixin, db.Model):
    __tablename__ = "system_settings"
    key = db.Column(db.String(120), primary_key=True)
    value = db.Column(db.Text, nullable=True)
    brand_logo_storage_object_id = db.Column(db.BigInteger, db.ForeignKey("storage_objects.id"), nullable=True)
    brand_logo_storage_object = db.relationship("StorageObject", foreign_keys=[brand_logo_storage_object_id])
