from datetime import datetime
from pathlib import Path
from sqlalchemy import func
from app.audit import audit
from app.extensions import db
from app.models import (CompanyMediaAlbum, CompanyMediaAlbumPermission, CompanyMediaFile, Role,
    StorageDerivative, UploadBatchItem, User, UserRole)
from app.storage.services import create_upload_batch_presign, complete_upload_item

class CompanyMediaError(ValueError): pass
ALBUM_PERMISSION_FLAGS = ("can_view", "can_upload", "can_edit", "can_delete", "can_download", "can_share")
_TRUE_VALUES = {True, 1, "1", "true", "on", "yes"}
_FALSE_VALUES = {False, 0, "0", "false", "off", "no", ""}


def _principal_id(value):
    if isinstance(value, bool) or not str(value).isascii() or not str(value).isdigit():
        raise CompanyMediaError("Đối tượng phân quyền không hợp lệ.")
    value = int(value)
    if value <= 0:
        raise CompanyMediaError("Đối tượng phân quyền không hợp lệ.")
    return value


def _flag_value(values, flag):
    raw_values = values.getlist(flag) if hasattr(values, "getlist") else [values.get(flag)]
    if not raw_values:
        return False
    if len(raw_values) != 1:
        raise CompanyMediaError("Giá trị quyền không hợp lệ.")
    raw_value = raw_values[0]
    normalized = raw_value.strip().lower() if isinstance(raw_value, str) else raw_value
    try:
        if normalized in _TRUE_VALUES:
            return True
        if normalized in _FALSE_VALUES or raw_value is None:
            return False
    except TypeError:
        pass
    raise CompanyMediaError("Giá trị quyền không hợp lệ.")


def normalize_album_permission_flags(values):
    normalized = {flag: _flag_value(values, flag) for flag in ALBUM_PERMISSION_FLAGS}
    if not any(normalized.values()):
        raise CompanyMediaError("Hãy cấp ít nhất một quyền.")
    return normalized


def _permission_principal(principal_type, principal_id):
    if principal_type not in {"user", "role"}:
        raise CompanyMediaError("Đối tượng phân quyền không hợp lệ.")
    principal_id = _principal_id(principal_id)
    if principal_type == "user":
        principal = db.session.get(User, principal_id)
        if not principal:
            raise CompanyMediaError("Người dùng không tồn tại.")
        if not principal.is_active:
            raise CompanyMediaError("Người dùng đã ngừng hoạt động.")
    elif not db.session.get(Role, principal_id):
        raise CompanyMediaError("Vai trò không tồn tại.")
    return principal_id


def _principal_label(principal_type, principal):
    if principal_type == "user":
        return (principal.full_name or principal.username or f"Người dùng #{principal.id}").strip()
    return (principal.name or f"Vai trò #{principal.id}").strip()


def assignable_album_principal_options(user, album):
    """Return the smallest principal directory the actor may administer.

    Global administrators retain the established directory administration
    workflow.  A delegated album sharer sees only principals already attached
    to this album (plus their own principal), which is sufficient to maintain
    existing ACLs without exposing organization-wide directory data.
    """
    if user.role_code in {UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value}:
        users = User.query.filter_by(is_active=True).order_by(User.full_name, User.username).all()
        roles = Role.query.order_by(Role.name, Role.code).all()
        principals = [("user", item) for item in users] + [("role", item) for item in roles]
    else:
        principals = []
        for entry in album.permissions:
            principal = entry.user if entry.principal_type == "user" else entry.role
            if principal is not None:
                principals.append((entry.principal_type, principal))
        principals.append(("user", user))
        if user.role is not None:
            principals.append(("role", user.role))

    seen = set()
    options = []
    for principal_type, principal in principals:
        key = (principal_type, principal.id)
        if key in seen:
            continue
        seen.add(key)
        options.append({"type": principal_type, "id": principal.id, "label": _principal_label(principal_type, principal)})
    return options


def validate_assignable_album_principal(user, album, principal_type, principal_id):
    """Authoritative POST validation matching the minimized picker scope."""
    try:
        normalized_id = _principal_id(principal_id)
    except CompanyMediaError:
        raise CompanyMediaError("Đối tượng phân quyền không hợp lệ.") from None
    # Global administrators are entitled to the directory, including useful
    # lifecycle validation for an inactive selected account.
    if user.role_code in {UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value}:
        return _permission_principal(principal_type, normalized_id)
    if principal_type not in {"user", "role"} or not any(
        option["type"] == principal_type and option["id"] == normalized_id
        for option in assignable_album_principal_options(user, album)
    ):
        raise CompanyMediaError("Đối tượng phân quyền không hợp lệ.")
    return normalized_id


def validate_album_permission_grant(user, album, requested_flags):
    """Validate an ACL replacement before any row is changed.

    A non-admin's requested state must be a subset of capabilities currently
    exercisable on this album. This applies to direct and role principals,
    including the actor's own ACL, so a share flag cannot bootstrap broader
    access. The caller's current share right is evaluated before mutation.
    """
    from app.company_media.permissions import effective_album_capabilities, share_album

    if not share_album(user, album, True):
        raise CompanyMediaError("Bạn không có quyền chia sẻ album này.")
    normalized = normalize_album_permission_flags(requested_flags)
    ceiling = effective_album_capabilities(user, album)
    if any(enabled and flag not in ceiling for flag, enabled in normalized.items()):
        raise CompanyMediaError("Quyền được cấp vượt quá quyền hiện có của bạn.")
    return normalized
def _name(value):
    value=(value or "").strip()
    if not value or len(value)>255: raise CompanyMediaError("Tên không hợp lệ.")
    return value
def _active(query, model, status):
    if status=="active": return query.filter(model.is_active.is_(True), model.deleted_at.is_(None))
    if status=="archived": return query.filter((model.is_active.is_(False)) | model.deleted_at.is_not(None))
    return query
def albums(user,status="active",q=""):
    from app.company_media.permissions import view_album
    query=_active(CompanyMediaAlbum.query,status and CompanyMediaAlbum,status)
    if q: query=query.filter(CompanyMediaAlbum.name.ilike(f"%{q}%"))
    return [a for a in query.order_by(func.lower(CompanyMediaAlbum.name)).all() if view_album(user,a,status!="active")]
def files(user,album,status="active",q=""):
    from app.company_media.permissions import view_file
    query=_active(CompanyMediaFile.query.filter_by(album_id=album.id),CompanyMediaFile,status)
    if q: query=query.filter(CompanyMediaFile.display_name.ilike(f"%{q}%"))
    return [f for f in query.order_by(CompanyMediaFile.sort_order,CompanyMediaFile.created_at).all() if view_file(user,f,status!="active")]
def create_album(user,name,description="",restricted=False):
    name=_name(name)
    if CompanyMediaAlbum.query.filter(func.lower(CompanyMediaAlbum.name)==name.lower(),CompanyMediaAlbum.is_active.is_(True),CompanyMediaAlbum.deleted_at.is_(None)).first(): raise CompanyMediaError("Đã có album cùng tên.")
    a=CompanyMediaAlbum(name=name,description=(description or "").strip() or None,is_restricted=restricted,created_by_id=user.id);db.session.add(a);db.session.flush();audit("company_media.album.create","CompanyMediaAlbum",a.id);db.session.commit();return a
def rename_album(user,a,name): a.name=_name(name);a.updated_by_id=user.id;audit("company_media.album.rename","CompanyMediaAlbum",a.id);db.session.commit()
def archive_album(user,a): a.is_active=False;a.deleted_at=datetime.utcnow();a.updated_by_id=user.id;audit("company_media.album.archive","CompanyMediaAlbum",a.id);db.session.commit()
def restore_album(user,a): a.is_active=True;a.deleted_at=None;a.updated_by_id=user.id;audit("company_media.album.restore","CompanyMediaAlbum",a.id);db.session.commit()
def presign(user,a,items,selection_session_id=None): return create_upload_batch_presign(user=user,module_type="company_media",target_type="album",target_id=a.id,files=items,selection_session_id=selection_session_id)
def complete(user,a,item_id,payload):
    item=db.session.get(UploadBatchItem,item_id)
    if not item or item.upload_batch.module_type!="company_media" or item.upload_batch.target_id!=a.id: raise CompanyMediaError("Upload item không thuộc album.")
    result=complete_upload_item(user=user,upload_batch_item_id=item_id,checksum_sha256=payload.get("checksum_sha256"));obj=item.storage_object
    if not obj.mime_type.startswith(("image/","video/")): raise CompanyMediaError("Album chỉ nhận ảnh hoặc video.")
    media=CompanyMediaFile.query.filter_by(storage_object_id=obj.id).first() or CompanyMediaFile(album_id=a.id,storage_object_id=obj.id,display_name=obj.original_filename,media_type="image" if obj.mime_type.startswith("image/") else "video",created_by_id=user.id)
    db.session.add(media);db.session.flush();audit("company_media.file.create","CompanyMediaFile",media.id);db.session.commit()
    from app.media_processing.services import enqueue_media_processing_for_storage_object
    enqueue_media_processing_for_storage_object(obj.id);return {**result,"file":{"id":media.id,"display_name":media.display_name}}
def signed_preview(f,variant=None,user=None):
    if not f or not f.is_active or f.deleted_at:
        raise CompanyMediaError("Tệp chưa sẵn sàng.")
    obj=f.storage_object
    if not obj or obj.upload_status != "active" or obj.deleted_at is not None:
        raise CompanyMediaError("Tệp chưa sẵn sàng.")
    # View permission is intentionally limited to derivatives. In particular,
    # video ``preview``/``stream`` must never sign the original object; callers
    # with download authority use signed_download through its separate route.
    types=("thumbnail","preview") if obj.mime_type.startswith("image/") else ("poster",)
    for typ in types:
        d=StorageDerivative.query.filter_by(storage_object_id=obj.id,derivative_type=typ).filter(
            StorageDerivative.deleted_at.is_(None), StorageDerivative.object_key.is_not(None),
            StorageDerivative.object_key != "",
        ).first()
        if d:
            from app.storage.providers import get_storage_provider
            from app.storage.quota import ensure_bandwidth, record_download
            user=user or db.session.get(User, f.created_by_id)
            ensure_bandwidth(user, d.file_size, preview=True); record_download(user,kind="thumbnail" if d.derivative_type == "thumbnail" else "preview",source_type="thumbnail" if d.derivative_type == "thumbnail" else "preview",module="company-media",estimated_bytes=d.file_size,derivative_id=d.id,estimated_storage_egress_bytes=d.file_size,estimated_client_egress_bytes=d.file_size);db.session.commit()
            return {"ok":True,"kind":"image" if obj.mime_type.startswith("image/") else "video","url":get_storage_provider().create_presigned_download(d.bucket,d.object_key,300,"inline",f.display_name)["url"]}
    if obj.processing_status == "failed" and obj.mime_type.startswith("image/"):
        return {"ok":False,"status":"unavailable","message":"Không tạo được ảnh xem trước cho tệp này."}
    return {"ok":False,"status":"processing" if obj.processing_status in {"queued","processing"} else "unavailable","message":"Đang xử lý preview."}
def signed_download(f, user=None):
    from app.storage.providers import get_storage_provider
    from flask import current_app
    user=user or db.session.get(User, f.created_by_id)
    if f.storage_object.file_size > int(current_app.config["DOWNLOAD_SINGLE_FILE_MAX_BYTES"]): raise CompanyMediaError("Dung lượng tải xuống tối đa là 300 MB mỗi lần.")
    from app.storage.quota import ensure_bandwidth, record_download
    try: ensure_bandwidth(user,f.storage_object.file_size)
    except ValueError as exc: raise CompanyMediaError(str(exc))
    record_download(user,kind="original",source_type="original",module="company-media",estimated_bytes=f.storage_object.file_size,storage_object_id=f.storage_object_id,estimated_storage_egress_bytes=f.storage_object.file_size,estimated_client_egress_bytes=f.storage_object.file_size);db.session.commit()
    return get_storage_provider().create_presigned_download(f.storage_object.bucket,f.storage_object.object_key,300,"attachment",f.display_name)
def set_cover(user,a,media_id):
    f=db.session.get(CompanyMediaFile,media_id)
    if not f or f.album_id!=a.id or not f.is_active or f.deleted_at: raise CompanyMediaError("Ảnh bìa phải là media đang hoạt động trong album.")
    a.cover_media_id=f.id;a.updated_by_id=user.id;audit("company_media.album.cover","CompanyMediaAlbum",a.id);db.session.commit()
def set_permission(user,a,typ,pid,form):
    # Complete validation precedes lookup/create/assignment, so rejected
    # requests cannot partially rewrite an existing ACL row.
    pid = validate_assignable_album_principal(user, a, typ, pid)
    pid = _permission_principal(typ, pid)
    normalized = validate_album_permission_grant(user, a, form)
    key = typ + "_id"
    entries = CompanyMediaAlbumPermission.query.filter_by(
        album_id=a.id, principal_type=typ, **{key: pid}
    ).all()
    if len(entries) > 1:
        raise CompanyMediaError("Quyền chia sẻ không hợp lệ.")
    entry = entries[0] if entries else CompanyMediaAlbumPermission(
        album_id=a.id, principal_type=typ, created_by_id=user.id, **{key: pid}
    )
    for flag, enabled in normalized.items():
        setattr(entry, flag, enabled)
    db.session.add(entry)
    db.session.flush()
    audit("company_media.album.share", "CompanyMediaAlbum", a.id,
          new_values={"principal_type": typ, "principal_id": pid, "flags": normalized})
    db.session.commit()
    return entry


def remove_permission(user, album, permission_id):
    from app.company_media.permissions import share_album

    if not share_album(user, album, True):
        raise CompanyMediaError("Bạn không có quyền chia sẻ album này.")
    if isinstance(permission_id, bool) or not str(permission_id).isascii() or not str(permission_id).isdigit():
        raise CompanyMediaError("Không tìm thấy quyền chia sẻ.")
    entry = CompanyMediaAlbumPermission.query.filter_by(
        id=int(permission_id), album_id=album.id
    ).first()
    if not entry:
        raise CompanyMediaError("Không tìm thấy quyền chia sẻ.")
    db.session.delete(entry)
    audit("company_media.album.revoke", "CompanyMediaAlbum", album.id,
          old_values={"permission_id": entry.id})
    db.session.commit()
