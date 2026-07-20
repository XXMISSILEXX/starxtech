from datetime import datetime

from sqlalchemy import func

from app.audit import audit
from app.extensions import db
from app.models import ProjectDocumentFile, ProjectDocumentFolder, ProjectDocumentFolderPermission
from app.project_documents.permissions import can_create_project_document_folder, can_view_project_document_folder


class DocumentValidationError(ValueError):
    pass


def get_or_create_project_root_folder(project, user):
    root = ProjectDocumentFolder.query.filter_by(project_id=project.id, is_root=True).filter(ProjectDocumentFolder.deleted_at.is_(None)).first()
    if root:
        return root
    root = ProjectDocumentFolder(project_id=project.id, name="__ROOT__", is_root=True, created_by_id=user.id)
    db.session.add(root)
    db.session.flush()
    audit("document.folder.create", "ProjectDocumentFolder", root.id, new_values={"root": True, "project_id": project.id})
    db.session.commit()
    return root


def list_accessible_projects(user):
    from app.models import Project, ProjectUser
    query = Project.query.filter(Project.deleted_at.is_(None))
    if user.role_code not in {"SUPER_ADMIN", "ADMIN", "VIEWER_ADMIN"}:
        query = query.join(ProjectUser).filter(ProjectUser.user_id == user.id)
    return query.order_by(Project.name).all()


def list_folder_children(user, folder, status="active", search=""):
    query = folder.children.filter(ProjectDocumentFolder.is_root.is_(False))
    if status == "active":
        query = query.filter(ProjectDocumentFolder.is_active.is_(True), ProjectDocumentFolder.deleted_at.is_(None))
    elif status == "archived":
        query = query.filter((ProjectDocumentFolder.is_active.is_(False)) | (ProjectDocumentFolder.deleted_at.is_not(None)))
    if search:
        query = query.filter(ProjectDocumentFolder.name.ilike(f"%{search.strip()}%"))
    return [item for item in query.order_by(func.lower(ProjectDocumentFolder.name)).all() if can_view_project_document_folder(user, item, include_archived=status != "active")]


def list_folder_files(user, folder, status="active", search=""):
    query = ProjectDocumentFile.query.filter_by(folder_id=folder.id)
    if status == "active":
        query = query.filter(ProjectDocumentFile.is_active.is_(True), ProjectDocumentFile.deleted_at.is_(None))
    elif status == "archived":
        query = query.filter((ProjectDocumentFile.is_active.is_(False)) | (ProjectDocumentFile.deleted_at.is_not(None)))
    if search:
        query = query.filter(ProjectDocumentFile.display_name.ilike(f"%{search.strip()}%"))
    from app.project_documents.permissions import can_view_project_document_file
    return [item for item in query.order_by(func.lower(ProjectDocumentFile.display_name)).all() if can_view_project_document_file(user, item)]


def list_move_destinations(user, folder):
    """Return only active, visible folders the actor may use as a move target."""
    candidates = ProjectDocumentFolder.query.filter(
        ProjectDocumentFolder.project_id == folder.project_id,
        ProjectDocumentFolder.is_active.is_(True),
        ProjectDocumentFolder.deleted_at.is_(None),
    ).order_by(func.lower(ProjectDocumentFolder.name)).all()
    return [candidate for candidate in candidates
            if candidate.id != folder.id and not _is_descendant(candidate, folder)
            and can_view_project_document_folder(user, candidate)
            and can_create_project_document_folder(user, candidate)]


def _name(value):
    value = (value or "").strip()
    if not value or len(value) > 255 or "/" in value or "\\" in value or value in {".", ".."}:
        raise DocumentValidationError("Tên thư mục không hợp lệ.")
    return value


def _ensure_sibling_name(project_id, parent_id, name, exclude_id=None):
    query = ProjectDocumentFolder.query.filter(ProjectDocumentFolder.project_id == project_id, ProjectDocumentFolder.parent_id == parent_id,
        ProjectDocumentFolder.is_active.is_(True), ProjectDocumentFolder.deleted_at.is_(None), func.lower(ProjectDocumentFolder.name) == name.lower())
    if exclude_id:
        query = query.filter(ProjectDocumentFolder.id != exclude_id)
    if query.first():
        raise DocumentValidationError("Đã có thư mục cùng tên trong vị trí này.")


def create_folder(user, parent_folder, name, description=None, is_restricted=False):
    name = _name(name)
    if not parent_folder.is_active or parent_folder.deleted_at:
        raise DocumentValidationError("Không thể tạo trong thư mục đã lưu trữ.")
    _ensure_sibling_name(parent_folder.project_id, parent_folder.id, name)
    folder = ProjectDocumentFolder(project_id=parent_folder.project_id, parent_id=parent_folder.id, name=name, description=(description or "").strip() or None,
        is_restricted=bool(is_restricted), created_by_id=user.id, updated_by_id=user.id)
    db.session.add(folder); db.session.flush()
    audit("document.folder.create", "ProjectDocumentFolder", folder.id, new_values={"parent_id": folder.parent_id, "name": folder.name, "restricted": folder.is_restricted})
    db.session.commit()
    return folder


def rename_folder(user, folder, new_name):
    if folder.is_root:
        raise DocumentValidationError("Không thể đổi tên thư mục gốc.")
    name = _name(new_name); _ensure_sibling_name(folder.project_id, folder.parent_id, name, folder.id)
    old = folder.name; folder.name = name; folder.updated_by_id = user.id
    audit("document.folder.rename", "ProjectDocumentFolder", folder.id, old_values={"name": old}, new_values={"name": name}); db.session.commit(); return folder


def _is_descendant(candidate, folder):
    node = candidate
    while node is not None:
        if node.id == folder.id: return True
        node = node.parent
    return False


def move_folder(user, folder, new_parent):
    if folder.is_root: raise DocumentValidationError("Không thể di chuyển thư mục gốc.")
    if folder.project_id != new_parent.project_id: raise DocumentValidationError("Không thể di chuyển giữa các dự án.")
    if not new_parent.is_active or new_parent.deleted_at: raise DocumentValidationError("Không thể di chuyển vào thư mục đã lưu trữ.")
    if new_parent.id == folder.id or _is_descendant(new_parent, folder): raise DocumentValidationError("Không thể di chuyển thư mục vào chính nó hoặc thư mục con.")
    _ensure_sibling_name(folder.project_id, new_parent.id, folder.name, folder.id)
    old_parent = folder.parent_id; folder.parent_id = new_parent.id; folder.updated_by_id = user.id
    audit("document.folder.move", "ProjectDocumentFolder", folder.id, old_values={"parent_id": old_parent}, new_values={"parent_id": new_parent.id}); db.session.commit(); return folder


def archive_folder(user, folder):
    if folder.is_root: raise DocumentValidationError("Không thể lưu trữ thư mục gốc.")
    folder.is_active = False; folder.deleted_at = datetime.utcnow(); folder.updated_by_id = user.id
    audit("document.folder.archive", "ProjectDocumentFolder", folder.id); db.session.commit(); return folder


def restore_folder(user, folder):
    if folder.is_root: raise DocumentValidationError("Thư mục gốc không thể được khôi phục.")
    if not folder.parent or not folder.parent.is_active or folder.parent.deleted_at: raise DocumentValidationError("Hãy khôi phục thư mục cha trước.")
    _ensure_sibling_name(folder.project_id, folder.parent_id, folder.name, folder.id)
    folder.is_active = True; folder.deleted_at = None; folder.updated_by_id = user.id
    audit("document.folder.restore", "ProjectDocumentFolder", folder.id); db.session.commit(); return folder


def set_folder_permission(user, folder, principal_type, principal_id, flags):
    if principal_type not in {"user", "role"} or not str(principal_id).isdigit(): raise DocumentValidationError("Đối tượng phân quyền không hợp lệ.")
    query = ProjectDocumentFolderPermission.query.filter_by(folder_id=folder.id, **{principal_type + "_id": int(principal_id)})
    entry = query.first()
    if not entry:
        entry = ProjectDocumentFolderPermission(folder_id=folder.id, principal_type=principal_type, created_by_id=user.id, **{principal_type + "_id": int(principal_id)})
        db.session.add(entry)
    for flag in ("can_view", "can_upload", "can_edit", "can_delete", "can_share"):
        setattr(entry, flag, bool(flags.get(flag)))
    db.session.flush(); audit("document.folder.share", "ProjectDocumentFolder", folder.id, new_values={"principal_type": principal_type, "principal_id": int(principal_id)}); db.session.commit(); return entry


def remove_folder_permission(user, folder, permission_id):
    entry = ProjectDocumentFolderPermission.query.filter_by(id=permission_id, folder_id=folder.id).first()
    if not entry: raise DocumentValidationError("Không tìm thấy quyền chia sẻ.")
    db.session.delete(entry); audit("document.folder.revoke", "ProjectDocumentFolder", folder.id, old_values={"permission_id": permission_id}); db.session.commit()


def build_breadcrumb(user, folder):
    items = []
    while folder is not None:
        if not can_view_project_document_folder(user, folder): return []
        items.append(folder); folder = folder.parent
    return list(reversed(items))
