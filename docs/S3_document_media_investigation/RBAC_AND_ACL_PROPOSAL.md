# RBAC and ACL proposal

## Permission catalogue proposed

Project Documents: `modules.project_documents.access`; `project_document_folders.view/create/edit/delete/share`; `project_document_files.view/upload/edit/delete/download`.

Company Media: `modules.company_media.access`; `company_media_albums.view/create/edit/delete/share`; `company_media_files.view/upload/delete/download`.

`delete`, `share`, folder/album archive/restore and destructive object cleanup are dangerous. Restore can initially reuse `delete` for backwards-compatible lifecycle policy, but explicit `.restore` should be considered before implementation if separation is desired. `files.edit` is only metadata rename/caption/tags, not bytes replacement.

## Default grants proposed

| Role | Project Documents | Company Media |
|---|---|---|
| SUPER_ADMIN | Bypass as current policy | Bypass as current policy |
| ADMIN | All module permissions (including share/archive) | All module permissions |
| VIEWER_ADMIN | module access + folder/file view/download | module access + album/file view/download |
| PROJECT_MANAGER | access + folder/file view/create/edit/upload/download; no delete/share by default | none by default |
| REPORTER | access + folder/file view/upload/download for assigned projects; no folder edit/delete/share | none by default |

Whether PROJECT_MANAGER receives project document delete/share is a business decision. Default deny is safer; ADMIN can grant via RBAC only when operational ownership requires it. No default Company Media access for PM/REPORTER until business asks. Existing RBAC policy must not be changed during investigation.

## Effective authorization

Allow a request only when all applicable gates pass:

```text
authenticated active user
AND module access permission
AND resource action permission
AND project scope (Project Documents only)
AND effective folder/album ACL action
AND target is active/visible (or explicit archive permission for archived view)
```

For project documents, SUPER_ADMIN bypasses all. ADMIN passes project scope and may either bypass ACL or require a documented administrator override; recommend bypass ACL for recovery/audit, while still logging it. PROJECT_MANAGER/REPORTER must be assigned through `ProjectUser` before evaluating ACL. A root/default ACL policy is required; recommended: project assignments supply baseline view/upload for a project root, and a folder ACL only **adds** grants in MVP. If a truly restricted folder is needed, mark it `visibility=restricted`; then it requires matching ACL and parent assignment alone is insufficient.

For an inherited tree, evaluate the nearest explicit restricted ancestor first. An ACL entry applies to its folder subtree unless a child has `inherit_permissions=false`/restricted policy. To keep MVP simple, choose one: (A) all folders inherit root grants and ACL adds access; or (B) a folder has explicit `is_restricted`, and its matching ACL overrides inherited broad project access. Do not implement deny entries; absence of allow is denial. Explicit deny makes role/user conflicts, audit, and discovery substantially harder.

Company album ACL has no tree: role/user union grants an action. `manage` is not permission to upload/delete unless corresponding file action is also allowed; UI can show controls only where both gates pass.

## Scope helpers

Implement later as pure services, not decorators alone:

- `can_view_project_document_folder(user, folder)`
- `can_upload_project_document_folder(user, folder)`
- `can_manage_project_document_folder(user, folder, action)`
- `can_view_project_document_file(user, file)` / `can_download_...`
- `can_view_company_media_album(user, album)` and `can_*_company_media_file`

Helpers must calculate ACL in one query/batched preload where listing many records, cache only per request, and never trust UI filtering. Search, presign, completion and signed GET all call the same helpers.

## Batch and derivative rules

`presign-batch` requires exactly the same `files.upload` module permission and target upload ACL as one-file upload. `complete-upload` repeats both checks: strict policy blocks completion if permission was revoked after presign, leaves object pending for cleanup and does not enqueue a worker. Signed derivative URLs require the same view/download ACL as original; a derivative never grants access by itself.

ADMIN/SUPER_ADMIN recovery/audit behavior remains as proposed: SUPER_ADMIN bypasses; ADMIN recovery bypass must be explicit, logged and never inferred from a UI button. Batch/search results cannot expose unauthorized item names, states or counts.
