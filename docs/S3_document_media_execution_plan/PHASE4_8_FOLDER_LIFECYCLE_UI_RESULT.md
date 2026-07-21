# Phase 4.8 — Restore Folder Lifecycle UI

Project Documents restores the folder lifecycle controls without changing the
storage model, migrations, or behavior of Company Media, Daily Reports,
ReportAttachment, and Partner modules.

## Folder lifecycle

- Folder filtering uses `folder_status=active|archived|all`; file filtering
  remains independently controlled by `file_status=active|archived|all`.
- Search, both filter values, and lifecycle redirects retain their query
  context. Archiving returns to the active parent view and includes a link to
  the archived folder view. Restoring returns to the active parent view.
- Archive and restore remain metadata-only operations on
  `ProjectDocumentFolder.is_active` and `deleted_at`. They keep audit logging
  and never delete document-file records, storage-object records, or stored
  bytes.

## UI and authorization

- Every visible folder card has an Open menu action. Active cards can also
  show Rename, Move, Share, and Archive; archived cards can show Share and
  Restore. Each action is independently gated by RBAC, project scope, and
  restricted-folder ACL.
- The current-folder header offers Share, Rename, Archive, or Restore as
  appropriate. Root folders can never be archived.
- Archived folders remain browsable for actors with folder `view` permission,
  including their breadcrumb context.
- Archive requires `project_document_folders.delete`; restore requires the
  separate `project_document_folders.restore` permission. Both POST routes
  retain CSRF and backend `403` enforcement.
