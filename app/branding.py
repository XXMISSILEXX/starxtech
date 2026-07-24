"""Single source of truth for the private, display-only system brand."""
from flask import current_app

from app.models import SystemSetting
from app.storage.providers import get_storage_provider


def get_current_branding():
    setting = SystemSetting.query.filter_by(key="branding").first()
    obj = setting.brand_logo_storage_object if setting else None
    if not obj or obj.deleted_at is not None or obj.upload_status != "active":
        return {"setting": setting, "logo_url": None, "has_custom_logo": False}
    try:
        url = get_storage_provider().create_presigned_download(
            obj.bucket, obj.object_key, current_app.config["STORAGE_DOWNLOAD_URL_TTL_SECONDS"], "inline", obj.original_filename
        )["url"]
    except Exception:
        url = None
    return {"setting": setting, "logo_url": url, "has_custom_logo": bool(url)}


def get_branding_logo_preview_url():
    return get_current_branding()["logo_url"]
