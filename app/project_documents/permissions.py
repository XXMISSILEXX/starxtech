from app.project_memberships import is_project_admin, is_viewer_admin, user_has_project_capability


FOLDER_PERMISSION_CAPABILITIES = {
    "can_view": ("can_view_documents", "view", False),
    "can_upload": ("can_upload_documents", "upload", False),
    "can_edit": ("can_edit_documents", "edit", False),
    "can_delete": ("can_archive_documents", "delete", False),
    "can_share": ("can_share_documents", "share", True),
}


def _base(user, capability, project_id):
    if project_id is None:
        codes = {
            "can_view_documents": "project_document_folders.view", "can_upload_documents": "project_document_files.upload",
            "can_edit_documents": "project_document_folders.edit", "can_archive_documents": "project_document_files.delete",
            "can_restore_documents": "project_document_files.restore", "can_share_documents": "project_document_folders.share",
        }
        return bool(user and user.is_authenticated and user.is_active and (is_project_admin(user) or
            (is_viewer_admin(user) and capability == "can_view_documents") or
            (user.can("modules.project_documents.access") and user.can(codes.get(capability, "")))))
    return user_has_project_capability(user, project_id, capability)


def can_create_custom_root(user):
    return bool(user and user.is_authenticated and user.is_active and (is_project_admin(user) or user.can("project_documents.custom_roots.create")))


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


def effective_folder_capabilities(user, folder):
    """Return the capabilities the actor can exercise on this folder now.

    Each result includes both the project/RBAC capability and the ACL result
    at the nearest restriction anchor.  Inherited access may therefore be
    delegated only at the same strength; it cannot become a stronger direct
    ACL on a descendant.  Project administrators retain their existing
    administrative bypass through ``_can``.
    """
    if not user or not getattr(user, "is_authenticated", False) or not folder:
        return frozenset()
    return frozenset(
        flag for flag, (capability, action, include_archived) in FOLDER_PERMISSION_CAPABILITIES.items()
        if _can(user, folder, capability, action, include_archived=include_archived)
    )

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
