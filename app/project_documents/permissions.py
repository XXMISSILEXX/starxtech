from app.auth.permissions import ADMIN_ROLES, ASSIGNED_PROJECT_ROLES, _is_assigned_to_project
from app.models import UserRole


GLOBAL_READ_ROLES = ADMIN_ROLES | {UserRole.VIEWER_ADMIN.value}


def _base(user, permission, project_id):
    return bool(user and user.is_authenticated and user.is_active and user.can("modules.project_documents.access")
                and user.can(permission) and (user.role_code in GLOBAL_READ_ROLES or (user.role_code in ASSIGNED_PROJECT_ROLES and _is_assigned_to_project(project_id, user))))


def can_access_project_documents(user):
    return bool(user and user.is_authenticated and user.is_active and user.can("modules.project_documents.access"))


def _restriction_anchor(folder):
    current = folder
    while current is not None:
        if current.is_restricted:
            return current
        current = current.parent
    return None


def _acl_allows(user, folder, action):
    if user.role_code in ADMIN_ROLES or (user.role_code == UserRole.VIEWER_ADMIN.value and action == "view"):
        return True
    anchor = _restriction_anchor(folder)
    if anchor is None:
        return True
    flag = "can_" + action
    return any(getattr(entry, flag, False) for entry in anchor.permissions
               if (entry.user_id == user.id or entry.role_id == user.role_id))


def _can(user, folder, permission, action, include_archived=False):
    return bool(folder and (include_archived or (folder.is_active and folder.deleted_at is None))
                and _base(user, permission, folder.project_id) and _acl_allows(user, folder, action))


def can_view_project_document_folder(user, folder, include_archived=False):
    return _can(user, folder, "project_document_folders.view", "view", include_archived)
def can_create_project_document_folder(user, parent_folder): return _can(user, parent_folder, "project_document_folders.create", "edit")
def can_edit_project_document_folder(user, folder): return _can(user, folder, "project_document_folders.edit", "edit")
def can_delete_project_document_folder(user, folder): return _can(user, folder, "project_document_folders.delete", "delete")
def can_restore_project_document_folder(user, folder): return _can(user, folder, "project_document_folders.restore", "delete", include_archived=True)
def can_share_project_document_folder(user, folder, include_archived=False): return _can(user, folder, "project_document_folders.share", "share", include_archived)
def can_upload_project_document_folder(user, folder): return _can(user, folder, "project_document_files.upload", "upload")

def can_view_project_document_file(user, file, include_archived=False):
    return bool(file and (include_archived or (file.is_active and file.deleted_at is None)) and _can(user, file.folder, "project_document_files.view", "view", include_archived))

def can_download_project_document_file(user, file):
    return bool(file and file.is_active and file.deleted_at is None and _can(user, file.folder, "project_document_files.download", "view"))

def can_edit_project_document_file(user, file):
    return bool(file and file.is_active and file.deleted_at is None and _can(user, file.folder, "project_document_files.edit", "edit"))

def can_delete_project_document_file(user, file):
    return bool(file and file.is_active and file.deleted_at is None and _can(user, file.folder, "project_document_files.delete", "delete"))

def can_restore_project_document_file(user, file):
    return bool(file and _can(user, file.folder, "project_document_files.delete", "delete", include_archived=True))
