from app.auth.permissions import ADMIN_ROLES
from app.models import UserRole

def access(user): return bool(user and user.is_authenticated and user.is_active and user.can("modules.company_media.access"))
def _acl(user, album, action):
    if user.role_code in ADMIN_ROLES or (user.role_code == UserRole.VIEWER_ADMIN.value and action in {"view", "download"}) or not album.is_restricted: return True
    return any(getattr(item, "can_" + action, False) for item in album.permissions if item.user_id == user.id or item.role_id == user.role_id)
def _can(user, album, code, action, archived=False):
    if not user or (user.role_code == UserRole.VIEWER_ADMIN.value and action not in {"view", "download"}):
        return False
    return bool(album and (archived or (album.is_active and not album.deleted_at)) and access(user) and user.can(code) and _acl(user, album, action))
def create_album(user): return bool(access(user) and user.role_code != UserRole.VIEWER_ADMIN.value and user.can("company_media_albums.create"))
def view_album(user, album, archived=False): return _can(user, album, "company_media_albums.view", "view", archived)
def upload_album(user, album): return _can(user, album, "company_media_files.upload", "upload")
def edit_album(user, album): return _can(user, album, "company_media_albums.edit", "edit")
def delete_album(user, album): return _can(user, album, "company_media_albums.delete", "delete")
def restore_album(user, album): return _can(user, album, "company_media_albums.restore", "delete", True)
def share_album(user, album, archived=False): return _can(user, album, "company_media_albums.share", "share", archived)
def view_file(user, file, archived=False): return bool(file and _can(user, file.album, "company_media_files.view", "view", archived))
def download_file(user, file): return bool(file and file.is_active and not file.deleted_at and _can(user, file.album, "company_media_files.download", "download"))
def edit_file(user, file): return bool(file and file.is_active and not file.deleted_at and _can(user, file.album, "company_media_files.edit", "edit"))
def delete_file(user, file): return bool(file and file.is_active and not file.deleted_at and _can(user, file.album, "company_media_files.delete", "delete"))
def restore_file(user, file): return bool(file and _can(user, file.album, "company_media_files.restore", "delete", True))
