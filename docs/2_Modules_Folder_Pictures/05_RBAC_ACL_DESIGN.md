# RBAC + ACL Design

## 1. Permission catalogue

### Project Documents

```text
modules.project_documents.access

project_document_folders.view
project_document_folders.create
project_document_folders.edit
project_document_folders.delete
project_document_folders.share
project_document_folders.restore

project_document_files.view
project_document_files.upload
project_document_files.edit
project_document_files.delete
project_document_files.download
project_document_files.restore
```

### Company Media

```text
modules.company_media.access

company_media_albums.view
company_media_albums.create
company_media_albums.edit
company_media_albums.delete
company_media_albums.share
company_media_albums.restore

company_media_files.view
company_media_files.upload
company_media_files.delete
company_media_files.download
company_media_files.restore
```

`delete` means archive/lưu trữ in UI, not hard delete.

## 2. Default grants đề xuất

| Role | Project Documents | Company Media |
|---|---|---|
| SUPER_ADMIN | Bypass | Bypass |
| ADMIN | Full | Full |
| VIEWER_ADMIN | module access + view/download | module access + view/download |
| PROJECT_MANAGER | access + folder/file view/create/edit/upload/download for assigned projects; no delete/share by default | none by default |
| REPORTER | access + folder/file view/upload/download for assigned projects; no folder edit/delete/share | none by default |

## 3. Effective permission formula

### Project Documents

```text
authenticated active user
AND current_user.can("modules.project_documents.access")
AND current_user.can(action permission)
AND project scope passes
AND folder ACL passes
AND target lifecycle is visible for action
```

### Company Media

```text
authenticated active user
AND current_user.can("modules.company_media.access")
AND current_user.can(action permission)
AND album ACL passes
AND target lifecycle is visible for action
```

## 4. Folder ACL

Project folder permission flags:

```text
can_view
can_upload
can_edit
can_delete
can_share
```

MVP policy:

- ACL is allow-only.
- No explicit deny.
- Folder permission applies to subtree unless future restricted/inheritance policy overrides it.
- File inherits folder permission.
- Root baseline for assigned project:
  - PM/Reporter can view/upload according role.
  - Additional grants can be added per folder.
- For restricted folder phase later:
  - add `visibility=restricted` or `inherit_permissions=false`.

## 5. Album ACL

Album permission flags:

```text
can_view
can_upload
can_manage
can_delete
```

MVP:

- No folder tree.
- Role/user grants are unioned.
- `can_manage` means album metadata/share/archive, not file upload/delete unless corresponding module permission + album ACL allow.

## 6. Batch upload authorization

`presign-batch` requires:

```text
files.upload module permission
AND target upload ACL
AND quota/limit pass
```

`complete-upload` repeats the same checks.

Strict revoke policy:

- If permission revoked after presign, complete fails.
- Pending object remains for cleanup.
- No visible file.
- No Celery job.

## 7. Signed URLs

Original or derivative signed URL requires:

```text
files.view/download permission
AND target view ACL
AND object/file active
```

A derivative never grants access by itself.

## 8. Admin behavior

- SUPER_ADMIN bypass all.
- ADMIN may bypass ACL for recovery/audit if documented and logged.
- UI must not rely only on hiding buttons.
- Backend helper is authoritative.

## 9. Scope helpers

Implement services:

```text
can_view_project_document_folder(user, folder)
can_upload_project_document_folder(user, folder)
can_manage_project_document_folder(user, folder, action)
can_view_project_document_file(user, file)
can_download_project_document_file(user, file)

can_view_company_media_album(user, album)
can_upload_company_media_album(user, album)
can_manage_company_media_album(user, album, action)
can_view_company_media_file(user, file)
```

All list/search/presign/complete/signed-url calls must use the same helpers.
