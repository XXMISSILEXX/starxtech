from flask import abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
from app.company_media import bp
from app.company_media import permissions as p
from app.company_media import services as s
from app.models import CompanyMediaAlbum, CompanyMediaAlbumPermission, CompanyMediaFile, Role, User

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
    return render_template("company_media/index.html",albums=items,covers=covers,album_status=status,q=request.args.get("q",""),can_create=p.create_album(current_user))
@bp.post("/albums/create")
def create():
    if not p.create_album(current_user): abort(403)
    try: a=s.create_album(current_user,request.form.get("name"),request.form.get("description"),request.form.get("is_restricted")=="1")
    except s.CompanyMediaError as e: flash(str(e),"danger");return redirect(url_for("company_media.index"))
    return redirect(url_for("company_media.album",album_id=a.id))
@bp.get("/albums/<int:album_id>")
def album(album_id):
    a=CompanyMediaAlbum.query.get_or_404(album_id)
    if not p.view_album(current_user,a,True): abort(403)
    c=_ctx(); items=s.files(current_user,a,c["media_status"],c["q"]);active=a.is_active and not a.deleted_at
    return render_template("company_media/album.html",album=a,files=items,active=active,**c,can_upload=p.upload_album(current_user,a),can_edit=p.edit_album(current_user,a),can_delete=p.delete_album(current_user,a),can_restore=p.restore_album(current_user,a),can_share=p.share_album(current_user,a,not active),can_download={x.id:p.download_file(current_user,x) for x in items},can_edit_file={x.id:p.edit_file(current_user,x) for x in items},can_delete_file={x.id:p.delete_file(current_user,x) for x in items},can_restore_file={x.id:p.restore_file(current_user,x) for x in items})
@bp.post("/albums/<int:album_id>/rename")
def rename(album_id):
    a=CompanyMediaAlbum.query.get_or_404(album_id)
    if not p.edit_album(current_user,a): abort(403)
    try:s.rename_album(current_user,a,request.form.get("name"))
    except s.CompanyMediaError as e:flash(str(e),"danger")
    return redirect(url_for("company_media.album",album_id=a.id))
@bp.post("/albums/<int:album_id>/archive")
def archive(album_id):
    a=CompanyMediaAlbum.query.get_or_404(album_id)
    if not p.delete_album(current_user,a): abort(403)
    s.archive_album(current_user,a);return redirect(url_for("company_media.index",album_status="active"))
@bp.post("/albums/<int:album_id>/restore")
def restore(album_id):
    a=CompanyMediaAlbum.query.get_or_404(album_id)
    if not p.restore_album(current_user,a): abort(403)
    s.restore_album(current_user,a);return redirect(url_for("company_media.index",album_status="active"))
@bp.post("/albums/<int:album_id>/cover")
def cover(album_id):
    a=CompanyMediaAlbum.query.get_or_404(album_id)
    if not p.edit_album(current_user,a): abort(403)
    try:s.set_cover(current_user,a,request.form.get("media_id",type=int))
    except s.CompanyMediaError as e:flash(str(e),"danger")
    return redirect(url_for("company_media.album",album_id=a.id))
@bp.post("/albums/<int:album_id>/cover/clear")
def clear_cover(album_id):
    a=CompanyMediaAlbum.query.get_or_404(album_id)
    if not p.edit_album(current_user,a): abort(403)
    a.cover_media_id=None; s.db.session.commit();return redirect(url_for("company_media.album",album_id=a.id))
@bp.post("/albums/<int:album_id>/files/presign-batch")
def presign(album_id):
    a=CompanyMediaAlbum.query.get_or_404(album_id)
    if not p.upload_album(current_user,a):abort(403)
    try:return jsonify(s.presign(current_user,a,(request.get_json() or {}).get("files",[])))
    except Exception as e:return jsonify(error=str(e)),400
@bp.post("/albums/<int:album_id>/files/complete-upload")
def complete(album_id):
    a=CompanyMediaAlbum.query.get_or_404(album_id)
    if not p.upload_album(current_user,a):abort(403)
    data=request.get_json() or {};return jsonify(s.complete(current_user,a,int(data.get("upload_batch_item_id")),data))
@bp.post("/files/<int:file_id>/signed-preview")
def preview(file_id):
    f=CompanyMediaFile.query.get_or_404(file_id)
    if not p.view_file(current_user,f):abort(403)
    return jsonify(s.signed_preview(f,(request.get_json() or {}).get("variant")))
@bp.post("/files/<int:file_id>/signed-download")
def download(file_id):
    f=CompanyMediaFile.query.get_or_404(file_id)
    if not p.download_file(current_user,f):abort(403)
    return jsonify(s.signed_download(f))
@bp.post("/files/<int:file_id>/rename")
def file_rename(file_id):
    f=CompanyMediaFile.query.get_or_404(file_id)
    if not p.edit_file(current_user,f): abort(403)
    name=(request.form.get("display_name") or "").strip()
    if not name: flash("Tên media không hợp lệ.","danger")
    else: f.display_name=name;f.updated_by_id=current_user.id;s.db.session.commit()
    return redirect(url_for("company_media.album",album_id=f.album_id))
@bp.post("/files/<int:file_id>/archive")
def file_archive(file_id):
    f=CompanyMediaFile.query.get_or_404(file_id)
    if not p.delete_file(current_user,f):abort(403)
    f.is_active=False;f.deleted_at=__import__('datetime').datetime.utcnow();f.updated_by_id=current_user.id;s.db.session.commit();return redirect(url_for("company_media.album",album_id=f.album_id))
@bp.post("/files/<int:file_id>/restore")
def file_restore(file_id):
    f=CompanyMediaFile.query.get_or_404(file_id)
    if not p.restore_file(current_user,f) or not f.album.is_active:abort(403)
    f.is_active=True;f.deleted_at=None;f.updated_by_id=current_user.id;s.db.session.commit();return redirect(url_for("company_media.album",album_id=f.album_id))
def _bulk(album_id, action):
    a=CompanyMediaAlbum.query.get_or_404(album_id)
    if not p.view_album(current_user,a):abort(403)
    ids=(request.get_json() or {}).get("file_ids",[]); items=CompanyMediaFile.query.filter(CompanyMediaFile.album_id==a.id,CompanyMediaFile.id.in_(ids)).all(); result={action:[] if action=="downloads" else 0,"skipped":0,"forbidden":0}
    for f in items:
        allowed={"archived":p.delete_file(current_user,f),"restored":p.restore_file(current_user,f) and a.is_active,"downloads":p.download_file(current_user,f)}[action]
        if not allowed:result["forbidden"]+=1;continue
        if action=="archived": f.is_active=False;f.deleted_at=__import__('datetime').datetime.utcnow();result[action]+=1
        elif action=="restored": f.is_active=True;f.deleted_at=None;result[action]+=1
        else: result["downloads"].append({"id":f.id,**s.signed_download(f)})
    s.db.session.commit();return jsonify(ok=True,**result)
@bp.post("/albums/<int:album_id>/files/bulk-archive")
def bulk_archive(album_id): return _bulk(album_id,"archived")
@bp.post("/albums/<int:album_id>/files/bulk-restore")
def bulk_restore(album_id): return _bulk(album_id,"restored")
@bp.post("/albums/<int:album_id>/files/bulk-signed-download")
def bulk_download(album_id): return _bulk(album_id,"downloads")
@bp.route("/albums/<int:album_id>/permissions",methods=["GET","POST"])
def permissions(album_id):
    a=CompanyMediaAlbum.query.get_or_404(album_id)
    if not p.share_album(current_user,a,True):abort(403)
    if request.method=="POST":
        if request.form.get("remove_id"):
            entry=CompanyMediaAlbumPermission.query.filter_by(id=request.form.get("remove_id",type=int),album_id=a.id).first()
            if not entry: flash("Không tìm thấy quyền chia sẻ.","danger")
            else:s.db.session.delete(entry);s.db.session.commit()
        else:
            try:s.set_permission(current_user,a,request.form.get("principal_type"),request.form.get("principal_id"),request.form)
            except s.CompanyMediaError as e:flash(str(e),"danger")
        return redirect(url_for("company_media.permissions",album_id=a.id))
    users = User.query.filter_by(is_active=True).order_by(User.full_name, User.username).all()
    roles = Role.query.order_by(Role.name, Role.code).all()
    principal_options = [
        {"type": "user", "id": user.id, "name": user.full_name, "username": user.username,
         "email": user.email, "role": user.role.name if user.role else ""}
        for user in users
    ] + [
        {"type": "role", "id": role.id, "name": role.name, "description": role.description,
         "code": role.code}
        for role in roles
    ]
    return render_template("company_media/permissions.html", album=a, entries=a.permissions,
                           principal_options=principal_options)
