from sqlalchemy import or_

from app.auth.permissions import ADMIN_ROLES
from app.models import CompanyMediaAlbum, CompanyMediaAlbumPermission, UserRole


READ_ACTIONS = {"view", "download"}
ALBUM_PERMISSION_CAPABILITIES = {
    "can_view": ("company_media_albums.view", "view", False),
    "can_upload": ("company_media_files.upload", "upload", False),
    "can_edit": ("company_media_albums.edit", "edit", False),
    "can_delete": ("company_media_albums.delete", "delete", False),
    "can_download": ("company_media_files.download", "download", False),
    "can_share": ("company_media_albums.share", "share", True),
}


def _active_user(user):
    return bool(user and user.is_authenticated and user.is_active)


def has_module_access(user):
    return bool(_active_user(user) and user.can("modules.company_media.access"))


def has_album_acl(user):
    """Whether an active album has a direct or role-scoped ACL for this user."""
    if not _active_user(user):
        return False
    return CompanyMediaAlbumPermission.query.join(CompanyMediaAlbum).filter(
        CompanyMediaAlbum.is_active.is_(True),
        CompanyMediaAlbum.deleted_at.is_(None),
        or_(CompanyMediaAlbumPermission.user_id == user.id,
            CompanyMediaAlbumPermission.role_id == user.role_id),
        or_(CompanyMediaAlbumPermission.can_view.is_(True),
            CompanyMediaAlbumPermission.can_download.is_(True),
            CompanyMediaAlbumPermission.can_upload.is_(True),
            CompanyMediaAlbumPermission.can_edit.is_(True),
            CompanyMediaAlbumPermission.can_delete.is_(True),
            CompanyMediaAlbumPermission.can_share.is_(True)),
    ).first() is not None


def access(user):
    return bool(_active_user(user) and (
        user.role_code in ADMIN_ROLES | {UserRole.VIEWER_ADMIN.value}
        or has_module_access(user)
        or has_album_acl(user)
    ))


def _matching_acl_allows(user, album, action):
    return any(getattr(item, "can_" + action, False) for item in album.permissions
               if item.user_id == user.id or (user.role_id is not None and item.role_id == user.role_id))


def _acl(user, album, action):
    if user.role_code in ADMIN_ROLES or (user.role_code == UserRole.VIEWER_ADMIN.value and action in READ_ACTIONS) or not album.is_restricted:
        return True
    return _matching_acl_allows(user, album, action)


def _can(user, album, code, action, archived=False):
    if not _active_user(user) or (user.role_code == UserRole.VIEWER_ADMIN.value and action not in READ_ACTIONS):
        return False
    if not album or not (archived or (album.is_active and not album.deleted_at)):
        return False
    if user.role_code in ADMIN_ROLES:
        return user.can(code)
    if user.role_code == UserRole.VIEWER_ADMIN.value:
        return _acl(user, album, action)
    # A matching album ACL is a scoped access grant.  It deliberately makes
    # shared-only Company Media usable without a global module/action grant.
    if _matching_acl_allows(user, album, action):
        return True
    return bool(has_module_access(user) and user.can(code) and _acl(user, album, action))


def effective_album_capabilities(user, album):
    """Return the capabilities the actor can exercise on this album now.

    Company Media intentionally permits a matching ACL to be the actor's
    module access for this *one* album.  The album creator receives no
    implicit ACL bypass: their ceiling is still their current RBAC/ACL result.
    This preserves the existing scoped-sharing model while making delegated
    grants strictly monotonic.  Administrators retain their existing global
    capabilities through ``_can``.
    """
    if not _active_user(user) or not album:
        return frozenset()
    return frozenset(
        flag for flag, (code, action, allow_archived) in ALBUM_PERMISSION_CAPABILITIES.items()
        if _can(user, album, code, action, archived=allow_archived)
    )


def create_album(user): return bool(has_module_access(user) and user.role_code != UserRole.VIEWER_ADMIN.value and user.can("company_media_albums.create"))
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
