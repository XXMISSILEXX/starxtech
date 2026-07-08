from app.extensions import db


class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.now(),
        onupdate=db.func.now(),
    )


class CreatedAtMixin:
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())


class SoftDeleteMixin:
    deleted_at = db.Column(db.DateTime, nullable=True)
