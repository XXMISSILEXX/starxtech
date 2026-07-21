# Phase 4.7 — Project Documents UX Grid + Bulk Actions

Project Documents now presents files as a responsive card grid. Media cards load signed thumbnail/poster URLs at runtime; file cards keep only a compact name and preview status. Detailed metadata and signed URLs are not server-rendered into the page.

## Implemented

- Compact folder toolbar and responsive folder/file grids.
- Per-file kebab menu with only RBAC/ACL-authorized actions: quick preview, download, rename, archive, or restore.
- Rename modal changes only `ProjectDocumentFile.display_name`; it keeps an existing extension when omitted, rejects extension changes, and rejects duplicate active names in the same folder.
- Checkbox selection includes select-all for the server-rendered files in the current filter/search result, an indeterminate state for partial selection, and a selected card state. JSON POST bulk archive, restore, and signed-download endpoints are capped at 50 files, enforce each file's permission and folder ACL, and return partial-result summaries. Archive remains metadata-only and does not delete S3/MinIO objects or derivatives.
- Folder sharing is reachable from the current-folder toolbar and an authorized child-folder kebab menu. RBAC grants action types; Folder ACL restricts actions inside restricted folders and files inherit their folder ACL. This MVP has no file-level ACL.
- Image preview uses derivatives; browser-supported MP4/WebM uses a temporary signed inline URL in an HTML5 player; PDF uses a temporary signed inline URL in an iframe. Other document types remain download-only.
- CSP now adds the configured S3-compatible origin to `frame-src` as well as existing `connect-src`, `img-src`, and `media-src`, enabling a private signed PDF iframe without wildcard sources.

## Routes

- `POST /project-documents/folders/<folder_id>/files/bulk-archive`
- `POST /project-documents/folders/<folder_id>/files/bulk-restore`
- `POST /project-documents/folders/<folder_id>/files/bulk-signed-download`

All routes require authentication, CSRF, Project Documents module access, project scope, and applicable file/folder ACL checks.

## Permission codes

- Module: `modules.project_documents.access`
- Folder: `project_document_folders.view/create/edit/delete/share/restore`
- File: `project_document_files.view/upload/edit/delete/download/restore`

## Limitations

- Bulk download opens individual temporary downloads; it does not build a ZIP archive and warns when more than ten downloads are returned.
- No video transcode, PDF thumbnail generation, or Office document conversion is included.
- Company Media, Daily Reports/ReportAttachment, and Partner Management are unchanged.
