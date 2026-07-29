import io

from flask import abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from PIL import Image, ImageOps, UnidentifiedImageError

from app.account import bp
from app.display_images import (DisplayImageCleanupError, DisplayImageError,
                                finalize_display_image_change, remove_display_image,
                                replace_display_image)
from app.extensions import db
from app.extensions import limiter
from app.display_images import IMAGE_EXTENSIONS, MAX_DISPLAY_IMAGE_BYTES


@bp.route("/", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        try:
            change = replace_display_image(current_user, request.files.get("avatar"), attribute="avatar_storage_object", scope="account-profiles", user=current_user)
            db.session.commit()
        except DisplayImageError as exc:
            db.session.rollback(); flash(str(exc), "danger")
        else:
            try:
                finalize_display_image_change(change)
            except DisplayImageCleanupError:
                db.session.rollback()
                flash("Đã cập nhật ảnh đại diện; ảnh cũ đang chờ dọn dẹp.", "warning")
            else:
                flash("Đã cập nhật ảnh đại diện.", "success")
        return redirect(url_for("account.profile"))
    return render_template("account/profile.html")


@bp.post("/avatar/delete")
@login_required
def delete_avatar():
    change = remove_display_image(current_user, attribute="avatar_storage_object")
    db.session.commit()
    try:
        finalize_display_image_change(change)
    except DisplayImageCleanupError:
        db.session.rollback()
        flash("Đã xóa ảnh đại diện; ảnh cũ đang chờ dọn dẹp.", "warning")
    else:
        flash("Đã xóa ảnh đại diện.", "success")
    return redirect(url_for("account.profile"))


@bp.get("/avatar")
@login_required
def avatar():
    obj = current_user.avatar_storage_object
    if not obj or obj.deleted_at is not None or obj.upload_status != "active":
        abort(404)
    if not current_app.config["MEDIA_CACHE_ENABLED"]:
        from app.storage.providers import get_storage_provider
        url = get_storage_provider().create_presigned_download(obj.bucket, obj.object_key,
            current_app.config["STORAGE_DOWNLOAD_URL_TTL_SECONDS"], "inline", obj.original_filename)["url"]
        response = redirect(url)
        response.headers["Cache-Control"] = "no-store, private"
        response.headers["Pragma"] = "no-cache"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response
    from app.storage.cache import CacheSource, MediaCacheSourceMissing, serve_cached_source
    source = CacheSource(category="user-avatar", object_id=current_user.id, derivative_type="avatar",
        immutable_key=obj.object_key, version_id=obj.id, extension=obj.file_ext, mime_type=obj.mime_type,
        file_size=obj.file_size, bucket=obj.bucket)
    try:
        return serve_cached_source(source, cache_control="private, max-age=86400, immutable")
    except MediaCacheSourceMissing:
        abort(404)


@login_required
@limiter.limit("30 per minute")
def media_display_preview():
    """Ephemeral WebP preview.  It never creates a database/S3 object."""
    upload = request.files.get("image")
    name = (upload.filename if upload else "") or ""
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if extension not in IMAGE_EXTENSIONS:
        return {"message": "Chỉ cho phép tệp ảnh hợp lệ."}, 400
    raw = upload.read()
    if not raw or len(raw) > MAX_DISPLAY_IMAGE_BYTES:
        return {"message": "Ảnh phải có dung lượng từ 1 byte đến 10 MB."}, 400
    try:
        with Image.open(io.BytesIO(raw)) as probe: probe.verify()
        with Image.open(io.BytesIO(raw)) as source:
            image = ImageOps.exif_transpose(source); image.load(); image.thumbnail((768, 768), Image.Resampling.LANCZOS)
            if image.mode not in {"RGB", "RGBA"}: image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            output = io.BytesIO(); image.save(output, "WEBP", quality=86, method=4); output.seek(0)
    except (UnidentifiedImageError, OSError, ValueError):
        return {"message": "Không thể tạo xem trước cho ảnh này."}, 422
    return send_file(output, mimetype="image/webp", max_age=0)
