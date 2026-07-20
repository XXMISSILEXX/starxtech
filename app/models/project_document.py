from sqlalchemy import event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

from app.extensions import db
from app.models.mixins import TimestampMixin


DOCUMENT_ID = db.BigInteger().with_variant(db.Integer(), "sqlite")


class ProjectDocumentFolder(TimestampMixin, db.Model):
    __tablename__ = "project_document_folders"
    __table_args__ = (
        db.Index("idx_project_document_folders_parent", "project_id", "parent_id", "deleted_at"),
        db.Index("idx_project_document_folders_root", "project_id", "is_root"),
        db.Index("uq_project_document_folders_root", "project_id", unique=True,
                 postgresql_where=db.text("is_root = true AND deleted_at IS NULL"),
                 sqlite_where=db.text("is_root = 1 AND deleted_at IS NULL")),
    )
    id = db.Column(DOCUMENT_ID, primary_key=True)
    project_id = db.Column(DOCUMENT_ID, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    parent_id = db.Column(DOCUMENT_ID, db.ForeignKey("project_document_folders.id", ondelete="RESTRICT"), nullable=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_root = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    is_restricted = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    created_by_id = db.Column(DOCUMENT_ID, db.ForeignKey("users.id"), nullable=False)
    updated_by_id = db.Column(DOCUMENT_ID, db.ForeignKey("users.id"), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    deleted_at = db.Column(db.DateTime, nullable=True)

    project = db.relationship("Project", backref=db.backref("document_folders", lazy="dynamic"))
    parent = db.relationship("ProjectDocumentFolder", remote_side=[id], backref=db.backref("children", lazy="dynamic"))
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    updated_by = db.relationship("User", foreign_keys=[updated_by_id])
    files = db.relationship("ProjectDocumentFile", back_populates="folder")
    permissions = db.relationship("ProjectDocumentFolderPermission", back_populates="folder", cascade="all, delete-orphan")


class ProjectDocumentFile(TimestampMixin, db.Model):
    __tablename__ = "project_document_files"
    __table_args__ = (
        db.Index("idx_project_document_files_folder", "project_id", "folder_id", "deleted_at"),
        db.UniqueConstraint("storage_object_id", name="uq_project_document_files_storage_object"),
    )
    id = db.Column(DOCUMENT_ID, primary_key=True)
    project_id = db.Column(DOCUMENT_ID, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    folder_id = db.Column(DOCUMENT_ID, db.ForeignKey("project_document_folders.id", ondelete="RESTRICT"), nullable=False)
    storage_object_id = db.Column(DOCUMENT_ID, db.ForeignKey("storage_objects.id"), nullable=False)
    display_name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    tags = db.Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    created_by_id = db.Column(DOCUMENT_ID, db.ForeignKey("users.id"), nullable=False)
    updated_by_id = db.Column(DOCUMENT_ID, db.ForeignKey("users.id"), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    deleted_at = db.Column(db.DateTime, nullable=True)
    project = db.relationship("Project")
    folder = db.relationship("ProjectDocumentFolder", back_populates="files")
    storage_object = db.relationship("StorageObject")
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    updated_by = db.relationship("User", foreign_keys=[updated_by_id])


class ProjectDocumentFolderPermission(TimestampMixin, db.Model):
    __tablename__ = "project_document_folder_permissions"
    __table_args__ = (
        db.CheckConstraint("principal_type IN ('user', 'role')", name="ck_project_document_folder_permissions_principal"),
        db.CheckConstraint("(user_id IS NOT NULL AND role_id IS NULL) OR (user_id IS NULL AND role_id IS NOT NULL)", name="ck_project_document_folder_permissions_principal_xor"),
        db.UniqueConstraint("folder_id", "user_id", name="uq_project_document_folder_permissions_user"),
        db.UniqueConstraint("folder_id", "role_id", name="uq_project_document_folder_permissions_role"),
    )
    id = db.Column(DOCUMENT_ID, primary_key=True)
    folder_id = db.Column(DOCUMENT_ID, db.ForeignKey("project_document_folders.id", ondelete="CASCADE"), nullable=False)
    principal_type = db.Column(db.String(10), nullable=False)
    user_id = db.Column(DOCUMENT_ID, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    role_id = db.Column(DOCUMENT_ID, db.ForeignKey("roles.id", ondelete="CASCADE"), nullable=True)
    can_view = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_upload = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_edit = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_delete = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    can_share = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    created_by_id = db.Column(DOCUMENT_ID, db.ForeignKey("users.id"), nullable=False)
    folder = db.relationship("ProjectDocumentFolder", back_populates="permissions")
    user = db.relationship("User", foreign_keys=[user_id])
    role = db.relationship("Role", foreign_keys=[role_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])


@event.listens_for(db.session, "before_flush")
def validate_project_document_file_folder(session, flush_context, instances):
    """Prevent file metadata from being associated with a folder in another project."""
    for document_file in session.new.union(session.dirty):
        if not isinstance(document_file, ProjectDocumentFile) or not document_file.folder_id:
            continue
        folder = document_file.folder or session.get(ProjectDocumentFolder, document_file.folder_id)
        if folder is not None and folder.project_id != document_file.project_id:
            raise ValueError("ProjectDocumentFile.folder must belong to the same project.")
