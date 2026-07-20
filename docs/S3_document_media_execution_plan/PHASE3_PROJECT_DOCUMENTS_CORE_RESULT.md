# Phase 3 — Project Documents Core Result

## Summary

Implemented the Project Documents core only: project folder tree, lazy project root, metadata-only file model, folder ACL, browse pages and lifecycle operations. No file bytes, presign endpoint, Celery enqueue or Company Media code is included.

## Files changed

- `app/models/project_document.py`, `app/models/__init__.py`
- `app/project_documents/__init__.py`, `permissions.py`, `services.py`, `routes.py`
- `app/templates/project_documents/index.html`, `folder.html`, `permissions.html`
- `app/permissions/registry.py`, `app/auth/permissions.py`, `app/__init__.py`, `app/ui.py`
- `app/templates/base.html`, `app/templates/modules/index.html`, `app/modules/routes.py`
- `migrations/versions/20260720_0012_add_project_documents_core.py`
- `tests/test_project_documents_core.py`

## Models and migration

Migration `20260720_0012_add_project_documents_core.py` creates `ProjectDocumentFolder`, `ProjectDocumentFile` and `ProjectDocumentFolderPermission`. It is additive and does not modify `ReportAttachment`, reports, Partner tables, StorageObject or worker tables.

Folders use an adjacency list and partial PostgreSQL unique indexes for one active root per project and case-insensitive active sibling names. Services repeat these validations for SQLite tests.

## Permissions and default grants

Added `modules.project_documents.access`, folder `view/create/edit/delete/share/restore`, and file `view/upload/edit/delete/download/restore` permissions.

- ADMIN receives all via the existing full-registry default.
- VIEWER_ADMIN: access, folder view, file view/download.
- PROJECT_MANAGER: access, folder view/create/edit, file view/upload/edit/download for assigned projects.
- REPORTER: access, folder/file view and file upload/download for assigned projects.
- SUPER_ADMIN remains policy bypass.

Run `flask sync-permissions` to register metadata and review before `flask sync-permissions --apply-defaults` to add missing grants. Neither command is run automatically.

## Routes/UI

Added `/project-documents`, project root browse, folder browse, create, rename, move, archive, restore and GET/POST ACL routes. State changes are POST and therefore protected by the existing CSRF extension. The UI has a selector, breadcrumb, search, folder browse, empty file placeholder and share page.

Folder browse now includes the `status=active|archived|all` filter. Archived folders display an archived badge and an authorized restore action. Each editable active child has a Bootstrap move modal; its destination list contains only active folders in the same project that are visible and valid for the actor's destination-create policy, including the project root.

## ACL and lifecycle

Active assigned PM/Reporter users receive root baseline through RBAC/project assignment. Normal folders inherit it. A restricted folder, including descendants, needs a matching allow-only user or role ACL; no ACL means no disclosure. ADMIN/SUPER_ADMIN retain recovery/audit bypass per existing policy. Archive is soft metadata lifecycle; roots cannot be moved or archived; moves reject cross-project, self, descendant, inactive destination and duplicate names.

VIEWER_ADMIN is a global read-only Project Documents role: it does not require a `ProjectUser` assignment, can lazily ensure and browse each project root, and can view restricted folder/file metadata. Its normal registry permissions still deny all folder mutations and sharing.

Restore uses the existing delete/archive policy and is backend-authorized. A child cannot be restored while its parent is archived; the service blocks it with “Hãy khôi phục thư mục cha trước.”

## Tests / known limitations

Added core tests for lazy root, role baseline, case-insensitive duplicate protection, cycles, move validation, archive filtering/restore parent policy, backend route authorization and restricted ACL. Upload UI, batch/presign integration, signed URLs, actual file metadata creation and Celery processing intentionally remain for Phase 4. Company Media remains unimplemented.
