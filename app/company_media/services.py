from datetime import datetime
from pathlib import Path
from sqlalchemy import func
from app.audit import audit
from app.extensions import db
from app.models import CompanyMediaAlbum, CompanyMediaAlbumPermission, CompanyMediaFile, Role, StorageDerivative, UploadBatchItem, User
from app.storage.services import create_upload_batch_presign, complete_upload_item

class CompanyMediaError(ValueError): pass
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
    obj=f.storage_object; types=("thumbnail","preview") if obj.mime_type.startswith("image/") else ("poster",)
    if obj.mime_type in {"video/mp4", "video/webm"} and variant in {"preview", "stream"}:
        from app.storage.providers import get_storage_provider
        from app.storage.quota import ensure_bandwidth, record_download
        user=user or db.session.get(User, f.created_by_id)
        ensure_bandwidth(user,obj.file_size,preview=True);record_download(user,kind="preview",estimated_bytes=obj.file_size,storage_object_id=obj.id);db.session.commit()
        return {"ok":True,"status":"ready","kind":"video","mime_type":obj.mime_type,"url":get_storage_provider().create_presigned_download(obj.bucket,obj.object_key,300,"inline",f.display_name)["url"]}
    for typ in types:
        d=StorageDerivative.query.filter_by(storage_object_id=obj.id,derivative_type=typ).filter(StorageDerivative.deleted_at.is_(None)).first()
        if d:
            from app.storage.providers import get_storage_provider
            from app.storage.quota import ensure_bandwidth, record_download
            user=user or db.session.get(User, f.created_by_id)
            ensure_bandwidth(user, d.file_size, preview=True); record_download(user,kind="preview",estimated_bytes=d.file_size,derivative_id=d.id);db.session.commit()
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
    record_download(user,kind="original",estimated_bytes=f.storage_object.file_size,storage_object_id=f.storage_object_id);db.session.commit()
    return get_storage_provider().create_presigned_download(f.storage_object.bucket,f.storage_object.object_key,300,"attachment",f.display_name)
def set_cover(user,a,media_id):
    f=db.session.get(CompanyMediaFile,media_id)
    if not f or f.album_id!=a.id or not f.is_active or f.deleted_at: raise CompanyMediaError("Ảnh bìa phải là media đang hoạt động trong album.")
    a.cover_media_id=f.id;a.updated_by_id=user.id;audit("company_media.album.cover","CompanyMediaAlbum",a.id);db.session.commit()
def set_permission(user,a,typ,pid,form):
    if typ not in {"user","role"} or not str(pid).isdigit(): raise CompanyMediaError("Đối tượng phân quyền không hợp lệ.")
    pid=int(pid)
    if pid <= 0:
        raise CompanyMediaError("Đối tượng phân quyền không hợp lệ.")
    if typ == "user":
        principal = db.session.get(User, pid)
        if not principal:
            raise CompanyMediaError("Người dùng không tồn tại.")
        if not principal.is_active:
            raise CompanyMediaError("Người dùng đã ngừng hoạt động.")
    elif not db.session.get(Role, pid):
        raise CompanyMediaError("Vai trò không tồn tại.")
    flags=("can_view","can_upload","can_edit","can_delete","can_download","can_share")
    if not any(bool(form.get(flag)) for flag in flags): raise CompanyMediaError("Hãy cấp ít nhất một quyền.")
    key=typ+"_id"; entry=CompanyMediaAlbumPermission.query.filter_by(album_id=a.id,principal_type=typ,**{key:pid}).first() or CompanyMediaAlbumPermission(album_id=a.id,principal_type=typ,created_by_id=user.id,**{key:pid})
    for flag in flags: setattr(entry,flag,bool(form.get(flag)))
    db.session.add(entry);db.session.commit();return entry
