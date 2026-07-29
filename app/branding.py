"""Single source of truth for the private, display-only system brand."""
from flask import abort, current_app, redirect, url_for
from flask_login import login_required

from app.models import SystemSetting


def _active_logo():
    setting = SystemSetting.query.filter_by(key="branding").first()
    obj = setting.brand_logo_storage_object if setting else None
    return setting, obj if obj and obj.deleted_at is None and obj.upload_status == "active" else None


def get_current_branding():
    setting, obj = _active_logo()
    if not obj:
        return {"setting": setting, "logo_url": None, "has_custom_logo": False}
    return {"setting": setting, "logo_url": url_for("branding.logo", v=obj.id), "has_custom_logo": True}


def get_branding_logo_preview_url():
    return get_current_branding()["logo_url"]


@login_required
def logo():
    """Stable, authorised delivery for the current private system logo."""
    _setting, obj = _active_logo()
    if not obj:
        abort(404)
    if not current_app.config["MEDIA_CACHE_ENABLED"]:
        from app.storage.providers import get_storage_provider
        return redirect(get_storage_provider().create_presigned_download(
            obj.bucket, obj.object_key, current_app.config["STORAGE_DOWNLOAD_URL_TTL_SECONDS"], "inline", obj.original_filename
        )["url"])
    from app.storage.cache import CacheSource, MediaCacheSourceMissing, serve_cached_source
    source = CacheSource(category="branding-logo", object_id=obj.id, derivative_type="logo",
        immutable_key=obj.object_key, version_id=obj.id, extension=obj.file_ext, mime_type=obj.mime_type,
        file_size=obj.file_size, bucket=obj.bucket)
    try:
        return serve_cached_source(source, cache_control="private, max-age=86400, immutable")
    except MediaCacheSourceMissing:
        abort(404)
