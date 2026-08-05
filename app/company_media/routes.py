from flask import abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
from app.audit import audit
from app.company_media import bp
from app.company_media import permissions as p
from app.company_media import services as s
from app.extensions import db
from app.models import CompanyMediaAlbum, CompanyMediaFile, StorageDerivative
from app.models import BulkDownloadJob
from app.bulk_downloads.services import (BulkDownloadError, parse_file_ids, preflight_media_download,
    request_media_download, stream_zip_download, serialize_job)
from app.storage.services import create_upload_selection_session, finalize_upload_selection_session
from app.company_media.upload_cleanup import cancel_company_media_upload_session
from app.storage.company_media_errors import error_envelope, upload_error
from app.storage.exceptions import (StorageAuthorizationError, StorageNotFoundError, StorageUploadContractError,
                                    StorageValidationError)
from app.storage.limits import get_company_media_upload_limits
from app.storage.downloads import SignedDownloadError, error_payload

def _one(model, ident): return db.get_or_404(model, ident)


def _file_audit_snapshot(media):
    storage = media.storage_object
    return {
        "file_name": media.display_name,
        "original_filename": storage.original_filename if storage else None,
        "created_by_id": media.created_by_id,
        "created_at": media.created_at.isoformat() if media.created_at else None,
        "file_size": storage.file_size if storage else None,
        "storage_object_id": media.storage_object_id,
        "object_key": storage.object_key if storage else None,
        "album_id": media.album_id,
    }


def _file_batch_audit_snapshot(album, snapshots):
    return {
        "album_id": album.id,
        "file_count": len(snapshots),
        "total_size_bytes": sum(snapshot["file_size"] or 0 for snapshot in snapshots),
        "files": snapshots,
    }


def _format_upload_bytes(value):
    """Render the public Company Media limits before its JS has initialized."""
    value = int(value)
    for unit in ("GiB", "MiB", "KiB"):
        divisor = {"GiB": 1024 ** 3, "MiB": 1024 ** 2, "KiB": 1024}[unit]
        if value >= divisor:
            amount = value / divisor
            return f"{amount:.2f}".rstrip("0").rstrip(".") + f" {unit}"
    return f"{value} B"


def _upload_error_response(error, *, fallback_code="upload_validation_failed", status_code=422):
    if isinstance(error, StorageUploadContractError):
        return jsonify(error_envelope(error)), error.status_code
    normalized = upload_error(fallback_code, str(error), status_code=status_code)
    return jsonify(error_envelope(normalized)), status_code

def _ctx():
    status=request.values.get("media_status","active").lower(); return {"q":request.values.get("q","").strip(),"media_status":status if status in {"active","archived","all"} else "active"}
@bp.before_request
def guard():
    if not p.access(current_user): abort(403)
@bp.get("/")
@bp.get("")
def index():
    status=request.args.get("album_status","active").lower();status=status if status in {"active","archived","all"} else "active"
    items=s.albums(current_user,status,request.args.get("q","")); covers={}
    for album in items:
        custom=CompanyMediaFile.query.filter_by(id=album.cover_media_id,album_id=album.id,is_active=True).filter(CompanyMediaFile.deleted_at.is_(None)).first() if album.cover_media_id else None
        covers[album.id]=custom or CompanyMediaFile.query.filter_by(album_id=album.id,is_active=True).filter(CompanyMediaFile.deleted_at.is_(None)).order_by(CompanyMediaFile.created_at).first()
    return render_template("company_media/index.html",albums=items,covers=covers,thumbnail_version_by_file=_thumbnail_versions(covers.values()),album_status=status,q=request.args.get("q",""),can_create=p.create_album(current_user))
@bp.post("/albums/create")
def create():
    if not p.create_album(current_user): abort(403)
    try: a=s.create_album(current_user,request.form.get("name"),request.form.get("description"),request.form.get("is_restricted")=="1")
    except s.CompanyMediaError as e: flash(str(e),"danger");return redirect(url_for("company_media.index"))
    return redirect(url_for("company_media.album",album_id=a.id))
@bp.get("/albums/<int:album_id>")
def album(album_id):
    a=_one(CompanyMediaAlbum, album_id)
    if not p.view_album(current_user,a,True): abort(403)
    c=_ctx(); items=s.files(current_user,a,c["media_status"],c["q"]);active=a.is_active and not a.deleted_at
    limits = get_company_media_upload_limits()
    limit_labels = {key: _format_upload_bytes(limits[key]) for key in (
        "max_selection_bytes", "max_image_bytes", "max_video_bytes", "max_batch_bytes",
    )}
    return render_template("company_media/album.html",album=a,files=items,active=active,thumbnail_version_by_file=_thumbnail_versions(items),company_media_upload_limits=limits,company_media_upload_limit_labels=limit_labels,**c,can_upload=p.upload_album(current_user,a),can_edit=p.edit_album(current_user,a),can_delete=p.delete_album(current_user,a),can_restore=p.restore_album(current_user,a),can_share=p.share_album(current_user,a,not active),can_download={x.id:p.download_file(current_user,x) for x in items},can_edit_file={x.id:p.edit_file(current_user,x) for x in items},can_delete_file={x.id:p.delete_file(current_user,x) for x in items},can_restore_file={x.id:p.restore_file(current_user,x) for x in items})
@bp.post("/albums/<int:album_id>/rename")
def rename(album_id):
    a=_one(CompanyMediaAlbum, album_id)
    if not p.edit_album(current_user,a): abort(403)
    try:s.rename_album(current_user,a,request.form.get("name"))
    except s.CompanyMediaError as e:flash(str(e),"danger")
    return redirect(url_for("company_media.album",album_id=a.id))
@bp.post("/albums/<int:album_id>/archive")
def archive(album_id):
    a=_one(CompanyMediaAlbum, album_id)
    if not p.delete_album(current_user,a): abort(403)
    s.archive_album(current_user,a);return redirect(url_for("company_media.index",album_status="active"))
@bp.post("/albums/<int:album_id>/restore")
def restore(album_id):
    a=_one(CompanyMediaAlbum, album_id)
    if not p.restore_album(current_user,a): abort(403)
    s.restore_album(current_user,a);return redirect(url_for("company_media.index",album_status="active"))
@bp.post("/albums/<int:album_id>/cover")
def cover(album_id):
    a=_one(CompanyMediaAlbum, album_id)
    if not p.edit_album(current_user,a): abort(403)
    try:s.set_cover(current_user,a,request.form.get("media_id",type=int))
    except s.CompanyMediaError as e:flash(str(e),"danger")
    return redirect(url_for("company_media.album",album_id=a.id))
@bp.post("/albums/<int:album_id>/cover/clear")
def clear_cover(album_id):
    a=_one(CompanyMediaAlbum, album_id)
    if not p.edit_album(current_user,a): abort(403)
    a.cover_media_id=None; s.db.session.commit();return redirect(url_for("company_media.album",album_id=a.id))
@bp.post("/albums/<int:album_id>/files/presign-batch")
def presign(album_id):
    a=_one(CompanyMediaAlbum, album_id)
    if not p.upload_album(current_user,a):abort(403)
    try:
        data=request.get_json() or {}; return jsonify(s.presign(current_user,a,data.get("files",[]),data.get("selection_session_id")))
    except StorageAuthorizationError: abort(403)
    except (StorageValidationError, s.CompanyMediaError) as exc:
        return _upload_error_response(exc)
    except Exception as exc:
        # Provider exceptions may contain bucket names, object keys, bearer
        # URLs, or provider response text.  Log only a stable event/context.
        current_app.logger.error("company_media_presign_failed event=CM-PRESIGN-001 album_id=%s actor_id=%s exception_type=%s",
                                 a.id, current_user.id, type(exc).__name__)
        return _upload_error_response(upload_error("presign_unavailable", "Không thể chuẩn bị tải tệp. Vui lòng thử lại sau.", retryable=True, status_code=502))
@bp.post("/albums/<int:album_id>/files/upload-selection-sessions")
def selection(album_id):
    a=_one(CompanyMediaAlbum, album_id)
    if not p.upload_album(current_user,a): abort(403)
    data=request.get_json() or {}
    try:return jsonify(create_upload_selection_session(user=current_user,module_type="company_media",target_type="album",target_id=a.id,declared_files=data.get("file_count"),declared_size_bytes=data.get("total_size_bytes")))
    except StorageValidationError as e:return _upload_error_response(e)
@bp.post("/albums/<int:album_id>/files/upload-selection-sessions/<int:session_id>/finalize")
def selection_finalize(album_id,session_id):
    a=_one(CompanyMediaAlbum, album_id)
    if not p.upload_album(current_user,a): abort(403)
    data = request.get_json(silent=True) or {}
    try:return jsonify(finalize_upload_selection_session(user=current_user,selection_session_id=session_id,module_type="company_media",target_type="album",target_id=a.id,failed_upload_batch_item_ids=data.get("failed_upload_batch_item_ids")))
    except StorageAuthorizationError: abort(403)
    except StorageValidationError as e:return _upload_error_response(e)
@bp.post("/albums/<int:album_id>/upload-sessions/<int:session_id>/cancel")
def selection_cancel(album_id, session_id):
    a = _one(CompanyMediaAlbum, album_id)
    if not p.upload_album(current_user, a):
        abort(403)
    try:
        summary = cancel_company_media_upload_session(
            actor=current_user, album_id=a.id, session_id=session_id,
        )
        db.session.commit()
        return jsonify(ok=True, **summary.as_dict())
    except StorageAuthorizationError:
        db.session.rollback()
        abort(403)
    except StorageValidationError as exc:
        db.session.rollback()
        return _upload_error_response(exc, fallback_code="upload_session_not_cancellable", status_code=409)
@bp.post("/albums/<int:album_id>/files/complete-upload")
def complete(album_id):
    a=_one(CompanyMediaAlbum, album_id)
    if not p.upload_album(current_user,a):abort(403)
    data=request.get_json(silent=True) or {}
    try:
        item_id = int(data.get("upload_batch_item_id"))
    except (TypeError, ValueError):
        return _upload_error_response(upload_error("invalid_upload_batch_item_id", "upload_batch_item_id không hợp lệ."))
    try:
        return jsonify(s.complete(current_user,a,item_id,data))
    except StorageAuthorizationError:
        abort(403)
    except (StorageValidationError, StorageNotFoundError, s.CompanyMediaError) as exc:
        return _upload_error_response(exc, fallback_code="upload_item_not_found" if isinstance(exc, StorageNotFoundError) else "upload_completion_failed", status_code=404 if isinstance(exc, StorageNotFoundError) else 422)
@bp.post("/files/<int:file_id>/signed-preview")
def preview(file_id):
    f=_one(CompanyMediaFile, file_id)
    if not p.view_file(current_user,f):abort(403)
    try:return jsonify(s.signed_preview(f,(request.get_json() or {}).get("variant"),current_user))
    except s.CompanyMediaError as e:return jsonify(error=str(e)),400
@bp.get("/files/<int:file_id>/thumbnail")
def thumbnail(file_id):
    f=_one(CompanyMediaFile, file_id)
    if not f.is_active or f.deleted_at or not p.view_file(current_user,f): abort(403)
    derivative=_thumbnail_derivative(f)
    if derivative is None: return _thumbnail_placeholder()
    if not current_app.config["MEDIA_CACHE_ENABLED"]:
        from app.storage.providers import get_storage_provider
        return redirect(get_storage_provider().create_presigned_download(derivative.bucket,derivative.object_key,current_app.config["STORAGE_DOWNLOAD_URL_TTL_SECONDS"],"inline",f.display_name)["url"])
    from app.storage.cache import CacheSource, MediaCacheSourceMissing, serve_cached_source
    source=CacheSource(category="company-media-thumbnail",object_id=f.id,derivative_type=derivative.derivative_type,immutable_key=derivative.object_key,version_id=derivative.id,extension=derivative.file_ext,mime_type=derivative.mime_type,file_size=derivative.file_size,bucket=derivative.bucket)
    cache_control="private, max-age=3600" if request.args.get("v")==str(derivative.id) else "private, max-age=0, must-revalidate"
    try:return serve_cached_source(source,cache_control=cache_control)
    except MediaCacheSourceMissing: abort(404)
@bp.post("/files/<int:file_id>/signed-download")
def download(file_id):
    f=_one(CompanyMediaFile, file_id)
    if not p.download_file(current_user,f):abort(403)
    try:return jsonify(s.signed_download(f,current_user))
    except SignedDownloadError as e:
        current_app.logger.warning("signed_download_failed event=CM-SIGNED-DOWNLOAD module=company_media file_id=%s actor_id=%s status=%s category=%s", f.id, current_user.id, e.status_code, e.category)
        return jsonify(error_payload(e)), e.status_code
    except s.CompanyMediaError as e:return jsonify(error=str(e)),400


def _thumbnail_derivative(f):
    obj=f.storage_object
    if not obj or obj.upload_status!="active" or obj.deleted_at is not None:return None
    kinds=("thumbnail",) if obj.mime_type.startswith("image/") else ("poster",) if obj.mime_type.startswith("video/") else ()
    if not kinds:return None
    return StorageDerivative.query.filter(StorageDerivative.storage_object_id==obj.id,StorageDerivative.derivative_type.in_(kinds),StorageDerivative.deleted_at.is_(None),StorageDerivative.object_key.is_not(None),StorageDerivative.object_key!="").first()


def _thumbnail_versions(files):
    object_to_file={f.storage_object_id:f.id for f in files if f and f.is_active and not f.deleted_at}
    if not object_to_file:return {}
    rows=StorageDerivative.query.filter(StorageDerivative.storage_object_id.in_(object_to_file),StorageDerivative.derivative_type.in_(("thumbnail","poster")),StorageDerivative.deleted_at.is_(None),StorageDerivative.object_key.is_not(None),StorageDerivative.object_key!="").all()
    return {object_to_file[row.storage_object_id]:row.id for row in rows}


def _thumbnail_placeholder():
    from pathlib import Path
    from flask import send_file
    response=send_file(Path(current_app.static_folder)/"img"/"attachment-processing.svg",mimetype="image/svg+xml",max_age=0)
    response.headers["Cache-Control"]="no-store, private";response.headers["X-Content-Type-Options"]="nosniff"
    return response
@bp.post("/files/<int:file_id>/rename")
def file_rename(file_id):
    f=_one(CompanyMediaFile, file_id)
    if not p.edit_file(current_user,f): abort(403)
    name=(request.form.get("display_name") or "").strip()
    if not name: flash("Tên media không hợp lệ.","danger")
    else: f.display_name=name;f.updated_by_id=current_user.id;s.db.session.commit()
    return redirect(url_for("company_media.album",album_id=f.album_id))
@bp.post("/files/<int:file_id>/archive")
def file_archive(file_id):
    f=_one(CompanyMediaFile, file_id)
    if not p.delete_file(current_user,f):abort(403)
    snapshot=_file_audit_snapshot(f);f.is_active=False;f.deleted_at=__import__('datetime').datetime.utcnow();f.updated_by_id=current_user.id;audit("company_media.file.delete","CompanyMediaFile",f.id,old_values=snapshot,new_values={"archived":True});s.db.session.commit();return redirect(url_for("company_media.album",album_id=f.album_id))
@bp.post("/files/<int:file_id>/restore")
def file_restore(file_id):
    f=_one(CompanyMediaFile, file_id)
    if not p.restore_file(current_user,f) or not f.album.is_active:abort(403)
    snapshot=_file_audit_snapshot(f);f.is_active=True;f.deleted_at=None;f.updated_by_id=current_user.id;audit("company_media.file.restore","CompanyMediaFile",f.id,old_values=snapshot,new_values={"restored":True});s.db.session.commit();return redirect(url_for("company_media.album",album_id=f.album_id))
def _bulk(album_id, action):
    a=_one(CompanyMediaAlbum, album_id)
    if not p.view_album(current_user,a):abort(403)
    try: ids=parse_file_ids(request)
    except BulkDownloadError as exc: return jsonify(error=str(exc)),400
    items=CompanyMediaFile.query.filter(CompanyMediaFile.album_id==a.id,CompanyMediaFile.id.in_(ids)).order_by(CompanyMediaFile.id).all(); result={action:0,"skipped":0,"forbidden":0}; snapshots=[]
    for f in items:
        allowed={"archived":p.delete_file(current_user,f),"restored":p.restore_file(current_user,f) and a.is_active}[action]
        if not allowed:result["forbidden"]+=1;continue
        snapshot=_file_audit_snapshot(f)
        if action=="archived": f.is_active=False;f.deleted_at=__import__('datetime').datetime.utcnow();f.updated_by_id=current_user.id;snapshots.append(snapshot);result[action]+=1
        elif action=="restored": f.is_active=True;f.deleted_at=None;f.updated_by_id=current_user.id;snapshots.append(snapshot);result[action]+=1
    if snapshots:
        batch_snapshot=_file_batch_audit_snapshot(a,snapshots)
        if action=="archived": audit("company_media.file.delete","CompanyMediaFile",old_values=batch_snapshot,new_values={"archived":True,"bulk":True})
        elif action=="restored": audit("company_media.file.restore","CompanyMediaFile",old_values=batch_snapshot,new_values={"restored":True,"bulk":True})
    s.db.session.commit();return jsonify(ok=True,**result)
@bp.post("/albums/<int:album_id>/files/bulk-archive")
def bulk_archive(album_id): return _bulk(album_id,"archived")
@bp.post("/albums/<int:album_id>/files/bulk-restore")
def bulk_restore(album_id): return _bulk(album_id,"restored")
@bp.post("/albums/<int:album_id>/files/bulk-signed-download")
def bulk_download(album_id):
    a=_one(CompanyMediaAlbum, album_id)
    if not p.view_album(current_user,a): abort(403)
    try:
        file_ids = parse_file_ids(request)
        result = request_media_download(current_user, a, file_ids)
        return stream_zip_download(current_user, result) if result["kind"] == "zip" else jsonify(ok=True, **result)
    except PermissionError:
        abort(403)
    except BulkDownloadError as exc:
        return jsonify(error=str(exc)), 400

@bp.post("/albums/<int:album_id>/files/bulk-download-validate")
def bulk_download_validate(album_id):
    a=_one(CompanyMediaAlbum, album_id)
    if not p.view_album(current_user,a): abort(403)
    try:
        return jsonify(ok=True, **preflight_media_download(current_user, a, parse_file_ids(request)))
    except PermissionError:
        abort(403)
    except BulkDownloadError as exc:
        return jsonify(error=str(exc)), 400

@bp.get("/bulk-download-jobs/<int:job_id>")
def bulk_download_status(job_id):
    job=_one(BulkDownloadJob, job_id)
    try: return jsonify(ok=True, **serialize_job(current_user,job))
    except PermissionError: abort(403)
@bp.route("/albums/<int:album_id>/permissions",methods=["GET","POST"])
def permissions(album_id):
    a=_one(CompanyMediaAlbum, album_id)
    if not p.share_album(current_user,a,True):abort(403)
    if request.method=="POST":
        if request.form.get("remove_id"):
            try:s.remove_permission(current_user,a,request.form.get("remove_id"))
            except s.CompanyMediaError as e:return jsonify(error=str(e)),400
        else:
            try:s.set_permission(current_user,a,request.form.get("principal_type"),request.form.get("principal_id"),request.form)
            except s.CompanyMediaError as e:return jsonify(error=str(e)),400
        return redirect(url_for("company_media.permissions",album_id=a.id))
    principal_options = s.assignable_album_principal_options(current_user, a)
    return render_template("company_media/permissions.html", album=a, entries=a.permissions,
                           principal_options=principal_options)
