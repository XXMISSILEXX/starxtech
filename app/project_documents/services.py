from datetime import datetime
from pathlib import Path

from sqlalchemy import func

from app.audit import audit
from app.extensions import db
from app.models import (ProjectDocumentFile, ProjectDocumentFolder, ProjectDocumentFolderPermission,
    Role, StorageDerivative, UploadBatchItem, User)
from app.project_documents.permissions import can_create_project_document_folder, can_view_project_document_folder
from app.storage.exceptions import StorageNotFoundError, StorageValidationError
from app.storage.services import complete_upload_item, create_upload_batch_presign


class DocumentValidationError(ValueError):
    pass


def get_or_create_project_root_folder(project, user):
    root = ProjectDocumentFolder.query.filter_by(project_id=project.id, is_root=True).filter(ProjectDocumentFolder.deleted_at.is_(None)).first()
    if root:
        return root
    root = ProjectDocumentFolder(project_id=project.id, name="__ROOT__", is_root=True, root_type="project", created_by_id=user.id)
    db.session.add(root)
    db.session.flush()
    audit("document.folder.create", "ProjectDocumentFolder", root.id, new_values={"root": True, "project_id": project.id})
    db.session.commit()
    return root


def create_custom_root_folder(user, name, description=None, is_restricted=False):
    name = (name or "").strip()
    if not name:
        raise DocumentValidationError("Tên mục hồ sơ là bắt buộc.")
    if ProjectDocumentFolder.query.filter_by(project_id=None, is_root=True, name=name).filter(ProjectDocumentFolder.deleted_at.is_(None)).first():
        raise DocumentValidationError("Đã có mục hồ sơ cùng tên.")
    root = ProjectDocumentFolder(project_id=None, name=name, description=(description or "").strip() or None,
        is_root=True, root_type="custom", is_restricted=is_restricted, created_by_id=user.id)
    db.session.add(root); db.session.flush(); audit("document.custom_root.create", "ProjectDocumentFolder", root.id, new_values={"name": name})
    db.session.commit(); return root


def list_accessible_projects(user):
    from app.models import Project
    from app.project_memberships import accessible_project_ids
    query = Project.query.filter(Project.deleted_at.is_(None))
    ids = accessible_project_ids(user, ("can_view_documents",))
    if ids is not None:
        query = query.filter(Project.id.in_(ids or [0]))
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
    return [item for item in query.order_by(func.lower(ProjectDocumentFile.display_name)).all() if can_view_project_document_file(user, item, include_archived=status != "active")]


def presign_folder_upload_batch(user, folder, files, selection_session_id=None, provider=None):
    from app.project_documents.permissions import can_upload_project_document_folder
    if not can_upload_project_document_folder(user, folder):
        raise DocumentValidationError("Bạn không có quyền tải tệp vào thư mục này.")
    return create_upload_batch_presign(user=user, module_type="project_documents", target_type="folder", target_id=folder.id, files=files, selection_session_id=selection_session_id, provider=provider)


def _display_name(value):
    value = (value or "").strip()
    if not value or len(value) > 255 or "/" in value or "\\" in value:
        raise DocumentValidationError("Tên hiển thị tệp không hợp lệ.")
    return value


def _normalized_rename_display_name(document_file, value):
    value = _display_name(value)
    existing_suffix = Path(document_file.display_name).suffix
    requested_suffix = Path(value).suffix
    if existing_suffix:
        if not requested_suffix:
            value = f"{value}{existing_suffix}"
        elif requested_suffix.lower() != existing_suffix.lower():
            raise DocumentValidationError("Không thể thay đổi phần mở rộng của tệp.")
    return value


def _ensure_file_display_name(folder_id, display_name, exclude_id=None):
    query = ProjectDocumentFile.query.filter(
        ProjectDocumentFile.folder_id == folder_id,
        ProjectDocumentFile.is_active.is_(True),
        ProjectDocumentFile.deleted_at.is_(None),
        func.lower(ProjectDocumentFile.display_name) == display_name.lower(),
    )
    if exclude_id is not None:
        query = query.filter(ProjectDocumentFile.id != exclude_id)
    if query.first():
        raise DocumentValidationError("Đã có tệp cùng tên trong thư mục này.")


def create_project_document_file_from_storage_object(user, folder, storage_object):
    if storage_object.upload_status != "active" or storage_object.deleted_at is not None:
        raise DocumentValidationError("Storage object chưa sẵn sàng.")
    if folder.project_id != getattr(folder, "project_id", None):
        raise DocumentValidationError("Thư mục không hợp lệ.")
    existing = ProjectDocumentFile.query.filter_by(storage_object_id=storage_object.id).first()
    if existing:
        return existing
    document_file = ProjectDocumentFile(project_id=folder.project_id, folder_id=folder.id, storage_object_id=storage_object.id,
        display_name=_display_name(storage_object.original_filename), created_by_id=user.id, updated_by_id=user.id)
    db.session.add(document_file); db.session.flush()
    audit("document.file.create", "ProjectDocumentFile", document_file.id, new_values={"folder_id": folder.id, "storage_object_id": storage_object.id})
    db.session.commit()
    return document_file


def complete_folder_upload_item(user, folder, upload_batch_item_id, metadata=None, provider=None):
    from app.project_documents.permissions import can_upload_project_document_folder
    if not can_upload_project_document_folder(user, folder):
        raise DocumentValidationError("Bạn không có quyền hoàn tất tải tệp vào thư mục này.")
    item = db.session.get(UploadBatchItem, upload_batch_item_id)
    if not item or item.upload_batch.module_type != "project_documents" or item.upload_batch.target_type != "folder" or item.upload_batch.target_id != folder.id:
        raise DocumentValidationError("Upload item không thuộc thư mục này.")
    completed = complete_upload_item(user=user, upload_batch_item_id=upload_batch_item_id, checksum_sha256=(metadata or {}).get("checksum_sha256"), provider=provider)
    document_file = create_project_document_file_from_storage_object(user, folder, item.storage_object)
    if item.storage_object.mime_type.startswith(("image/", "video/")):
        try:
            from app.media_processing.services import enqueue_media_processing_for_storage_object
            enqueue_media_processing_for_storage_object(item.storage_object_id)
        except Exception:
            # The original is already active; reconciliation can enqueue later.
            pass
    return {**completed, "file": file_payload(document_file)}


def file_payload(document_file):
    obj = document_file.storage_object
    return {"id": document_file.id, "display_name": document_file.display_name, "mime_type": obj.mime_type, "file_size": obj.file_size,
            "processing_status": obj.processing_status, "is_active": document_file.is_active}


def create_file_download_url(user, document_file, provider=None):
    from app.project_documents.permissions import can_download_project_document_file
    if not can_download_project_document_file(user, document_file):
        raise DocumentValidationError("Bạn không có quyền tải tệp này.")
    storage_object = document_file.storage_object
    if storage_object.upload_status != "active" or storage_object.deleted_at is not None:
        raise DocumentValidationError("Tệp chưa sẵn sàng.")
    from flask import current_app
    if storage_object.file_size > int(current_app.config["DOWNLOAD_SINGLE_FILE_MAX_BYTES"]):
        raise DocumentValidationError("Dung lượng tải xuống tối đa là 300 MB mỗi lần.")
    from app.storage.quota import ensure_bandwidth, record_download
    try: ensure_bandwidth(user, storage_object.file_size)
    except ValueError as exc: raise DocumentValidationError(str(exc))
    from app.storage.providers import get_storage_provider
    provider = provider or get_storage_provider()
    result = provider.create_presigned_download(storage_object.bucket, storage_object.object_key, 300, "attachment", document_file.display_name)
    audit("document.file.download", "ProjectDocumentFile", document_file.id)
    record_download(user, kind="original", estimated_bytes=storage_object.file_size, storage_object_id=storage_object.id)
    db.session.commit()
    return result


def create_file_preview_url(user, document_file, variant=None, provider=None):
    from app.project_documents.permissions import can_view_project_document_file
    if not can_view_project_document_file(user, document_file):
        raise DocumentValidationError("Bạn không có quyền xem trước tệp này.")

    mime_type = document_file.storage_object.mime_type
    if mime_type.startswith("image/"):
        derivative_types = {
            "thumbnail": ("thumbnail", "preview"),
            "preview": ("preview", "thumbnail"),
            None: ("preview", "thumbnail"),
        }.get(variant)
    elif mime_type in {"video/mp4", "video/webm"} and variant == "stream":
        storage_object = document_file.storage_object
        if storage_object.upload_status != "active" or storage_object.deleted_at is not None:
            raise DocumentValidationError("Tệp chưa sẵn sàng.")
        from app.storage.providers import get_storage_provider
        provider = provider or get_storage_provider()
        result = provider.create_presigned_download(storage_object.bucket, storage_object.object_key, 300, "inline", document_file.display_name)
        from app.storage.quota import ensure_bandwidth, record_download
        ensure_bandwidth(user, storage_object.file_size, preview=True); record_download(user, kind="preview", estimated_bytes=storage_object.file_size, storage_object_id=storage_object.id); db.session.commit()
        return {"ok": True, "status": "ready", "kind": "video", "mime_type": storage_object.mime_type, **result}
    elif mime_type.startswith("video/"):
        derivative_types = {"poster": ("poster",), None: ("poster",)}.get(variant)
    elif mime_type == "application/pdf" and variant in {None, "document"}:
        storage_object = document_file.storage_object
        if storage_object.upload_status != "active" or storage_object.deleted_at is not None:
            raise DocumentValidationError("Tệp chưa sẵn sàng.")
        from app.storage.providers import get_storage_provider
        provider = provider or get_storage_provider()
        result = provider.create_presigned_download(storage_object.bucket, storage_object.object_key, 300, "inline", document_file.display_name)
        from app.storage.quota import ensure_bandwidth, record_download
        ensure_bandwidth(user, storage_object.file_size, preview=True); record_download(user, kind="preview", estimated_bytes=storage_object.file_size, storage_object_id=storage_object.id); db.session.commit()
        return {"ok": True, "status": "ready", "kind": "pdf", "mime_type": storage_object.mime_type, **result}
    else:
        derivative_types = None
    if derivative_types is None:
        raise DocumentValidationError("Loại tệp này chưa hỗ trợ xem nhanh.")

    derivative = None
    for derivative_type in derivative_types:
        derivative = StorageDerivative.query.filter_by(
            storage_object_id=document_file.storage_object_id,
            derivative_type=derivative_type,
        ).filter(
            StorageDerivative.deleted_at.is_(None),
            StorageDerivative.object_key.is_not(None),
            StorageDerivative.object_key != "",
        ).first()
        if derivative:
            break
    if not derivative:
        if document_file.storage_object.processing_status in {"queued", "processing"}:
            return {"ok": False, "status": "processing", "message": "Đang xử lý preview."}
        if document_file.storage_object.processing_status == "failed" and mime_type.startswith("image/"):
            return {"ok": False, "status": "unavailable", "message": "Không tạo được ảnh xem trước cho tệp này."}
        return {"ok": False, "status": "unavailable", "message": "Chưa có preview."}
    from app.storage.providers import get_storage_provider
    provider = provider or get_storage_provider()
    result = provider.create_presigned_download(derivative.bucket, derivative.object_key, 300, "inline", document_file.display_name)
    from app.storage.quota import ensure_bandwidth, record_download
    ensure_bandwidth(user, derivative.file_size, preview=True); record_download(user, kind="preview", estimated_bytes=derivative.file_size, derivative_id=derivative.id); db.session.commit()
    return {"ok": True, "status": "ready", "kind": "image", "mime_type": derivative.mime_type, **result}


def rename_file(user, document_file, display_name):
    from app.project_documents.permissions import can_edit_project_document_file
    if not can_edit_project_document_file(user, document_file): raise DocumentValidationError("Bạn không có quyền đổi tên tệp này.")
    display_name = _normalized_rename_display_name(document_file, display_name)
    _ensure_file_display_name(document_file.folder_id, display_name, document_file.id)
    old = document_file.display_name; document_file.display_name = display_name; document_file.updated_by_id = user.id
    audit("document.file.rename", "ProjectDocumentFile", document_file.id, old_values={"display_name": old}, new_values={"display_name": document_file.display_name}); db.session.commit(); return document_file


def archive_file(user, document_file):
    from app.project_documents.permissions import can_delete_project_document_file
    if not can_delete_project_document_file(user, document_file): raise DocumentValidationError("Bạn không có quyền lưu trữ tệp này.")
    document_file.is_active = False; document_file.deleted_at = datetime.utcnow(); document_file.updated_by_id = user.id
    audit("document.file.archive", "ProjectDocumentFile", document_file.id); db.session.commit(); return document_file


def restore_file(user, document_file):
    from app.project_documents.permissions import can_restore_project_document_file
    if not can_restore_project_document_file(user, document_file): raise DocumentValidationError("Bạn không có quyền khôi phục tệp này.")
    if not document_file.folder.is_active or document_file.folder.deleted_at: raise DocumentValidationError("Hãy khôi phục thư mục cha trước.")
    document_file.is_active = True; document_file.deleted_at = None; document_file.updated_by_id = user.id
    audit("document.file.restore", "ProjectDocumentFile", document_file.id); db.session.commit(); return document_file


def _normalize_file_ids(file_ids):
    normalized = []
    for value in file_ids or []:
        try:
            file_id = int(value)
        except (TypeError, ValueError):
            continue
        if file_id > 0 and file_id not in normalized:
            normalized.append(file_id)
    if len(normalized) > 50:
        raise DocumentValidationError("Chỉ có thể thao tác tối đa 50 tệp một lần.")
    if not normalized:
        raise DocumentValidationError("Chưa chọn tệp hợp lệ.")
    return normalized


def _bulk_files_in_folder(folder, file_ids):
    return ProjectDocumentFile.query.filter(
        ProjectDocumentFile.folder_id == folder.id,
        ProjectDocumentFile.id.in_(_normalize_file_ids(file_ids)),
    ).all()


def bulk_archive_files(user, folder, file_ids):
    from app.project_documents.permissions import can_delete_project_document_file

    summary = {"archived": 0, "skipped": 0, "forbidden": 0}
    for document_file in _bulk_files_in_folder(folder, file_ids):
        if not document_file.is_active or document_file.deleted_at is not None:
            summary["skipped"] += 1
        elif not can_delete_project_document_file(user, document_file):
            summary["forbidden"] += 1
        else:
            document_file.is_active = False
            document_file.deleted_at = datetime.utcnow()
            document_file.updated_by_id = user.id
            audit("document.file.archive", "ProjectDocumentFile", document_file.id)
            summary["archived"] += 1
    db.session.commit()
    return summary


def bulk_restore_files(user, folder, file_ids):
    from app.project_documents.permissions import can_restore_project_document_file

    summary = {"restored": 0, "skipped": 0, "forbidden": 0}
    for document_file in _bulk_files_in_folder(folder, file_ids):
        if document_file.is_active and document_file.deleted_at is None:
            summary["skipped"] += 1
        elif not can_restore_project_document_file(user, document_file):
            summary["forbidden"] += 1
        elif not folder.is_active or folder.deleted_at:
            summary["skipped"] += 1
        else:
            document_file.is_active = True
            document_file.deleted_at = None
            document_file.updated_by_id = user.id
            audit("document.file.restore", "ProjectDocumentFile", document_file.id)
            summary["restored"] += 1
    db.session.commit()
    return summary


def bulk_file_download_urls(user, folder, file_ids, provider=None):
    from app.project_documents.permissions import can_download_project_document_file

    summary = {"downloads": [], "skipped": 0, "forbidden": 0}
    for document_file in _bulk_files_in_folder(folder, file_ids):
        if not document_file.is_active or document_file.deleted_at is not None:
            summary["skipped"] += 1
        elif not can_download_project_document_file(user, document_file):
            summary["forbidden"] += 1
        else:
            signed = create_file_download_url(user, document_file, provider=provider)
            summary["downloads"].append({"id": document_file.id, "display_name": document_file.display_name, **signed})
    return summary


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
    if principal_type not in {"user", "role"} or not str(principal_id).isdigit():
        raise DocumentValidationError("Đối tượng phân quyền không hợp lệ.")
    principal_id = int(principal_id)
    if principal_id <= 0:
        raise DocumentValidationError("Đối tượng phân quyền không hợp lệ.")
    if principal_type == "user":
        principal = db.session.get(User, principal_id)
        if not principal or not principal.is_active:
            raise DocumentValidationError("Người dùng không tồn tại hoặc đã ngừng hoạt động.")
    elif not db.session.get(Role, principal_id):
        raise DocumentValidationError("Vai trò không tồn tại.")

    permission_flags = ("can_view", "can_upload", "can_edit", "can_delete", "can_share")
    if not any(bool(flags.get(flag)) for flag in permission_flags):
        raise DocumentValidationError("Hãy cấp ít nhất một quyền cho đối tượng được chia sẻ.")

    query = ProjectDocumentFolderPermission.query.filter_by(
        folder_id=folder.id,
        principal_type=principal_type,
        **{principal_type + "_id": principal_id},
    )
    entry = query.first()
    if not entry:
        entry = ProjectDocumentFolderPermission(folder_id=folder.id, principal_type=principal_type,
            created_by_id=user.id, **{principal_type + "_id": principal_id})
        db.session.add(entry)
    for flag in permission_flags:
        setattr(entry, flag, bool(flags.get(flag)))
    db.session.flush(); audit("document.folder.share", "ProjectDocumentFolder", folder.id,
        new_values={"principal_type": principal_type, "principal_id": principal_id}); db.session.commit(); return entry


def remove_folder_permission(user, folder, permission_id):
    entry = ProjectDocumentFolderPermission.query.filter_by(id=permission_id, folder_id=folder.id).first()
    if not entry: raise DocumentValidationError("Không tìm thấy quyền chia sẻ.")
    db.session.delete(entry); audit("document.folder.revoke", "ProjectDocumentFolder", folder.id, old_values={"permission_id": permission_id}); db.session.commit()


def build_breadcrumb(user, folder):
    items = []
    while folder is not None:
        if not can_view_project_document_folder(user, folder, include_archived=True): return []
        items.append(folder); folder = folder.parent
    return list(reversed(items))
