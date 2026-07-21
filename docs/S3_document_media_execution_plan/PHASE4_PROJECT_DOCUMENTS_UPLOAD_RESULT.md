# Phase 4 — Project Documents Upload Result

## Summary

Project Documents now integrates the Phase 1 batch-presign/complete contract with Phase 3 folder ACL and creates `ProjectDocumentFile` metadata only after an object becomes active. No schema migration is needed.

## Routes and flow

- `POST /project-documents/folders/<id>/files/presign-batch`
- `POST /project-documents/folders/<id>/files/complete-upload`
- `POST /project-documents/files/<id>/signed-download`
- `POST /project-documents/files/<id>/signed-preview`
- `POST /project-documents/files/<id>/rename|archive|restore`

All mutations use CSRF and repeat folder/file RBAC + ACL checks. Completion validates the Phase 1 item belongs to the folder, calls HEAD-backed completion, creates one metadata row per active object, and enqueues image/video processing without blocking the completed original.

## UI and limitations

Folder browse includes a multiple-file upload input, per-item status text, metadata list, signed download, rename, archive and restore controls gated by backend permissions. Preview endpoint is implemented for image preview/video poster derivatives; the lightweight UI does not yet render a full modal/lightbox. Browser upload requires the configured private storage provider's CORS policy.

Phase 4.5 adds an accessible drag/drop queue, explicit upload action, per-file rejection/upload/complete errors, and S3-compatible readiness. See [PHASE4_5_S3_SMOKE_TEST_GUIDE.md](PHASE4_5_S3_SMOKE_TEST_GUIDE.md) for MinIO local setup and smoke checks.

Company Media is not implemented. ReportAttachment/Daily Reports and Partner remain unchanged. Phase 5 is Company Media core; future Project Documents polish can add upload retry/cancel/polling and a preview lightbox.
