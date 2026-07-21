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
def presign(user,a,items): return create_upload_batch_presign(user=user,module_type="company_media",target_type="album",target_id=a.id,files=items)
def complete(user,a,item_id,payload):
    item=db.session.get(UploadBatchItem,item_id)
    if not item or item.upload_batch.module_type!="company_media" or item.upload_batch.target_id!=a.id: raise CompanyMediaError("Upload item không thuộc album.")
    result=complete_upload_item(user=user,upload_batch_item_id=item_id,checksum_sha256=payload.get("checksum_sha256"));obj=item.storage_object
    if not obj.mime_type.startswith(("image/","video/")): raise CompanyMediaError("Album chỉ nhận ảnh hoặc video.")
    media=CompanyMediaFile.query.filter_by(storage_object_id=obj.id).first() or CompanyMediaFile(album_id=a.id,storage_object_id=obj.id,display_name=obj.original_filename,media_type="image" if obj.mime_type.startswith("image/") else "video",created_by_id=user.id)
    db.session.add(media);db.session.flush();audit("company_media.file.create","CompanyMediaFile",media.id);db.session.commit()
    from app.media_processing.services import enqueue_media_processing_for_storage_object
    enqueue_media_processing_for_storage_object(obj.id);return {**result,"file":{"id":media.id,"display_name":media.display_name}}
def signed_preview(f,variant=None):
    obj=f.storage_object; types=("thumbnail","preview") if obj.mime_type.startswith("image/") else ("poster",)
    if obj.mime_type in {"video/mp4", "video/webm"} and variant in {"preview", "stream"}:
        from app.storage.providers import get_storage_provider
        return {"ok":True,"status":"ready","kind":"video","mime_type":obj.mime_type,"url":get_storage_provider().create_presigned_download(obj.bucket,obj.object_key,300,"inline",f.display_name)["url"]}
    for typ in types:
        d=StorageDerivative.query.filter_by(storage_object_id=obj.id,derivative_type=typ).filter(StorageDerivative.deleted_at.is_(None)).first()
        if d:
            from app.storage.providers import get_storage_provider
            return {"ok":True,"kind":"image" if obj.mime_type.startswith("image/") else "video","url":get_storage_provider().create_presigned_download(d.bucket,d.object_key,300,"inline",f.display_name)["url"]}
    return {"ok":False,"status":"processing" if obj.processing_status in {"queued","processing"} else "unavailable","message":"Đang xử lý preview."}
def signed_download(f):
    from app.storage.providers import get_storage_provider
    return get_storage_provider().create_presigned_download(f.storage_object.bucket,f.storage_object.object_key,300,"attachment",f.display_name)
def set_cover(user,a,media_id):
    f=db.session.get(CompanyMediaFile,media_id)
    if not f or f.album_id!=a.id or not f.is_active or f.deleted_at: raise CompanyMediaError("Ảnh bìa phải là media đang hoạt động trong album.")
    a.cover_media_id=f.id;a.updated_by_id=user.id;audit("company_media.album.cover","CompanyMediaAlbum",a.id);db.session.commit()
def set_permission(user,a,typ,pid,form):
    if typ not in {"user","role"} or not str(pid).isdigit(): raise CompanyMediaError("Đối tượng phân quyền không hợp lệ.")
    pid=int(pid); key=typ+"_id"; entry=CompanyMediaAlbumPermission.query.filter_by(album_id=a.id,principal_type=typ,**{key:pid}).first() or CompanyMediaAlbumPermission(album_id=a.id,principal_type=typ,created_by_id=user.id,**{key:pid})
    for flag in ("can_view","can_upload","can_edit","can_delete","can_download","can_share"): setattr(entry,flag,bool(form.get(flag)))
    if not any(getattr(entry,x) for x in ("can_view","can_upload","can_edit","can_delete","can_download","can_share")): raise CompanyMediaError("Hãy cấp ít nhất một quyền.")
    db.session.add(entry);db.session.commit()
