from app.project_memberships import is_project_admin, is_viewer_admin, user_has_project_capability


def _base(user, capability, project_id):
    return user_has_project_capability(user, project_id, capability)


def can_access_project_documents(user):
    from app.auth.permissions import can_access_project_documents_module
    return can_access_project_documents_module(user)


def _restriction_anchor(folder):
    current = folder
    while current is not None:
        if current.is_restricted:
            return current
        current = current.parent
    return None


def _acl_allows(user, folder, action):
    if is_project_admin(user) or (is_viewer_admin(user) and action == "view"):
        return True
    anchor = _restriction_anchor(folder)
    if anchor is None:
        return True
    flag = "can_" + action
    return any(getattr(entry, flag, False) for entry in anchor.permissions
               if (entry.user_id == user.id or entry.role_id == user.role_id))


def _can(user, folder, capability, action, include_archived=False):
    return bool(folder and (include_archived or (folder.is_active and folder.deleted_at is None))
                and _base(user, capability, folder.project_id) and _acl_allows(user, folder, action))


def can_view_project_document_folder(user, folder, include_archived=False): return _can(user, folder, "can_view_documents", "view", include_archived)
def can_create_project_document_folder(user, parent_folder): return _can(user, parent_folder, "can_edit_documents", "edit")
def can_edit_project_document_folder(user, folder): return _can(user, folder, "can_edit_documents", "edit")
def can_delete_project_document_folder(user, folder): return _can(user, folder, "can_archive_documents", "delete")
def can_restore_project_document_folder(user, folder): return _can(user, folder, "can_restore_documents", "delete", include_archived=True)
def can_share_project_document_folder(user, folder, include_archived=False): return _can(user, folder, "can_share_documents", "share", include_archived)
def can_upload_project_document_folder(user, folder): return _can(user, folder, "can_upload_documents", "upload")

def can_view_project_document_file(user, file, include_archived=False):
    return bool(file and (include_archived or (file.is_active and file.deleted_at is None)) and _can(user, file.folder, "can_view_documents", "view", include_archived))

def can_download_project_document_file(user, file):
    return bool(file and file.is_active and file.deleted_at is None and _can(user, file.folder, "can_view_documents", "view"))

def can_edit_project_document_file(user, file):
    return bool(file and file.is_active and file.deleted_at is None and _can(user, file.folder, "can_edit_documents", "edit"))

def can_delete_project_document_file(user, file):
    return bool(file and file.is_active and file.deleted_at is None and _can(user, file.folder, "can_archive_documents", "delete"))

def can_restore_project_document_file(user, file):
    return bool(file and _can(user, file.folder, "can_restore_documents", "delete", include_archived=True))
