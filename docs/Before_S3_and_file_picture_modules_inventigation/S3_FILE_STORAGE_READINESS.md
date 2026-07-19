# S3 / file storage readiness

## Current state

Only report images exist. `app/reports/services.py` validates extension and Pillow content, normalizes/resizes to max 1920px, creates UUID filename, writes under configured `UPLOAD_ROOT/project_.../report_.../section_...`; `ReportAttachment` stores original/stored name, relative `file_path`, MIME, size, dimensions and uploader. `/attachments/<id>` checks project-read and constrains the resolved filesystem path below `UPLOAD_ROOT`. Compose mounts host uploads into the web container; it is not public. Images are limited to three active attachments per report section.

## Proposed abstraction

Introduce a small `StorageService` only when the new modules are implemented:

```python
put(stream, object_key, content_type) -> StoredObject
open(object_key) -> binary stream
delete(object_key) -> None
create_download_url(object_key, expires_in) -> str  # optional S3 implementation
```

`LocalStorageService` preserves private local-root semantics. `S3StorageService` uses private bucket and server credentials. Application services generate object keys, call storage, persist metadata in the DB transaction flow; add compensating cleanup/retry for an object written when DB commit fails.

Use opaque UUID-prefixed keys, e.g. `documents/project/<project_id>/<uuid>` and `event-photos/album/<album_id>/<uuid>`, never user filename or public URL as identity.

## File/object metadata

Create a shared `stored_objects` table or include equivalent fields in each attachment entity: `id`, `storage_backend` (`local`/`s3`), `bucket` nullable, `object_key` unique, `original_filename`, `content_type`, `size_bytes`, `sha256`, image width/height nullable, `uploaded_by_user_id`, `project_id` nullable, `department_id` nullable, `deleted_at`, timestamps. `project_documents` adds folder/category/title/status; `event_albums` and `event_photos` add album/tag visibility. Keep DB ID as download reference; client never receives object key unless unavoidable.

## Private access and audit

1. Lookup DB object by ID, deny deleted/missing.
2. Domain policy checks module permission plus `own|project|department|all` scope and folder/project/owner constraints.
3. Record audit for upload/download/delete (actor, object/entity, project, result; avoid signed URL/token in audit).
4. Stream via backend for small/strictly controlled content, or generate short-lived, response-content-disposition-bound presigned URL only after authorization. A presigned URL must not be stored as permanent metadata.

Separate metadata permission from byte download where policy needs it. Upload validates allowlist/MIME by content inspection, size, filename normalization, virus scanning policy (when available), image processing in temporary/private area, and cleanup. Preserve CSRF for browser POSTs.

## Future permissions

Documents: `documents.view`, `documents.upload`, `documents.edit_metadata`, `documents.delete`, `documents.download`, `documents.share`, `documents.manage_folders`, `documents.manage_settings`, `documents.view_project`, `documents.download_project`, `documents.upload_project`.

Event photos: `event_photos.view`, `event_photos.upload`, `event_photos.edit`, `event_photos.delete`, `event_photos.download`, `event_photos.manage_albums`, `event_photos.manage_settings`.

## Do not do

- Do not make bucket/object ACL public, expose a static S3 URL, or authorize from a guessed key.
- Do not trust extension/client MIME, persist presigned URLs, put credentials in source, or run upload storage as a public static directory.
- Do not hard-delete object before DB policy/retention decision; use soft-delete + queued final purge where retention requires it.
