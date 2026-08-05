from sqlalchemy import event
import sqlalchemy as sa

from app.extensions import db
from app.models.mixins import TimestampMixin
from app.models.project_document import DOCUMENT_ID


class CompanyMediaAlbum(TimestampMixin, db.Model):
    __tablename__ = "company_media_albums"
    __table_args__ = (
        db.Index("idx_company_media_albums_lifecycle", "deleted_at", "is_active"),
        db.Index(
            "uq_company_media_albums_active_name",
            sa.text("lower(name)"),
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL AND is_active"),
            sqlite_where=sa.text("deleted_at IS NULL AND is_active"),
        ),
    )
    id = db.Column(DOCUMENT_ID, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    cover_media_id = db.Column(DOCUMENT_ID, nullable=True)
    is_restricted = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    created_by_id = db.Column(DOCUMENT_ID, db.ForeignKey("users.id"), nullable=False)
    updated_by_id = db.Column(DOCUMENT_ID, db.ForeignKey("users.id"))
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    deleted_at = db.Column(db.DateTime)
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    updated_by = db.relationship("User", foreign_keys=[updated_by_id])
    files = db.relationship("CompanyMediaFile", back_populates="album")
    permissions = db.relationship("CompanyMediaAlbumPermission", back_populates="album", cascade="all, delete-orphan")


class CompanyMediaFile(TimestampMixin, db.Model):
    __tablename__ = "company_media_files"
    __table_args__ = (
        db.Index("idx_company_media_files_album", "album_id", "deleted_at", "is_active"),
    )
    id = db.Column(DOCUMENT_ID, primary_key=True)
    album_id = db.Column(DOCUMENT_ID, db.ForeignKey("company_media_albums.id", ondelete="RESTRICT"), nullable=False)
    storage_object_id = db.Column(DOCUMENT_ID, db.ForeignKey("storage_objects.id"), nullable=False, unique=True)
    display_name = db.Column(db.String(255), nullable=False)
    caption = db.Column(db.Text)
    media_type = db.Column(db.String(10), nullable=False)
    sort_order = db.Column(db.Integer)
    created_by_id = db.Column(DOCUMENT_ID, db.ForeignKey("users.id"), nullable=False)
    updated_by_id = db.Column(DOCUMENT_ID, db.ForeignKey("users.id"))
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    deleted_at = db.Column(db.DateTime)
    album = db.relationship("CompanyMediaAlbum", back_populates="files")
    storage_object = db.relationship("StorageObject")


class CompanyMediaAlbumPermission(TimestampMixin, db.Model):
    __tablename__ = "company_media_album_permissions"
    __table_args__ = (db.CheckConstraint("principal_type IN ('user', 'role')", name="ck_company_media_album_permissions_principal"), db.CheckConstraint("(user_id IS NOT NULL AND role_id IS NULL) OR (user_id IS NULL AND role_id IS NOT NULL)", name="ck_company_media_album_permissions_principal_xor"), db.UniqueConstraint("album_id", "user_id", name="uq_company_media_album_permissions_user"), db.UniqueConstraint("album_id", "role_id", name="uq_company_media_album_permissions_role"))
    id = db.Column(DOCUMENT_ID, primary_key=True)
    album_id = db.Column(DOCUMENT_ID, db.ForeignKey("company_media_albums.id", ondelete="CASCADE"), nullable=False)
    principal_type = db.Column(db.String(10), nullable=False)
    user_id = db.Column(DOCUMENT_ID, db.ForeignKey("users.id", ondelete="CASCADE"))
    role_id = db.Column(DOCUMENT_ID, db.ForeignKey("roles.id", ondelete="CASCADE"))
    can_view = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_upload = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_edit = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_delete = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_download = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_share = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    created_by_id = db.Column(DOCUMENT_ID, db.ForeignKey("users.id"), nullable=False)
    album = db.relationship("CompanyMediaAlbum", back_populates="permissions")
    user = db.relationship("User", foreign_keys=[user_id])
    role = db.relationship("Role", foreign_keys=[role_id])


@event.listens_for(db.session, "before_flush")
def validate_company_media_cover(session, flush_context, instances):
    for album in session.new.union(session.dirty):
        if isinstance(album, CompanyMediaAlbum) and album.cover_media_id:
            media = session.get(CompanyMediaFile, album.cover_media_id)
            if media and media.album_id != album.id:
                raise ValueError("Company media cover must belong to its album.")
