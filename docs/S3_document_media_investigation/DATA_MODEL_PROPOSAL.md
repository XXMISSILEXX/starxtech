# Data model proposal

## Shared storage

`storage_objects`: `id`, `bucket`, `object_key` unique, `thumbnail_object_key` nullable (compatibility/convenience only; canonical derivatives are below), `original_filename`, `mime_type`, `file_ext`, `file_size`, `checksum_sha256` nullable, `width`, `height`, `duration_seconds`, `uploaded_by_id`, `upload_status` (`pending|active|failed|deleted`), `processing_status` (`none|queued|processing|completed|failed`), `created_at`, `completed_at`, `deleted_at`. Add unique `(bucket, object_key)`, indexes `(upload_status, created_at)`, `(processing_status, created_at)`, uploader/status. `object_key` immutable after issuance.

`storage_derivatives`: `id`, `storage_object_id`, `derivative_type` (`thumbnail|preview|poster|video_preview`), bucket, object key, MIME, extension, size, width, height, duration, `created_by_job_id`, created/deleted timestamps. Unique active `(storage_object_id, derivative_type)`, unique `(bucket, object_key)`, index object/type. `video_preview` is reserved; no full video transcoding in MVP.

`media_processing_jobs`: `id`, `storage_object_id`, job type (`image_derivatives|video_derivatives`), status (`pending|processing|succeeded|failed|cancelled`), nullable `celery_task_id`, attempts/max_attempts, start/finish, error code/message, timestamps. Index `(status, created_at)`, `(storage_object_id, job_type)`, unique active job per object/type if retries are represented in the same row. PostgreSQL remains source of truth; Celery/Redis state is not authoritative.

`upload_batches`: `id`, module type (`project_documents|company_media`), target type (`folder|album`), target id, creator, total/accepted/completed/failed counters, status (`pending|uploading|completed|partial_failed|failed`), created/completed timestamps. `upload_batch_items`: batch FK, nullable storage object FK, client file id, original filename, MIME, size, status (`accepted|rejected|uploading|completed|failed|cancelled`), error message, timestamps; unique `(upload_batch_id, client_file_id)`.

`UploadBatchItem` is recommended for MVP rather than only `StorageObject.batch_id`: it captures rejected files that have no StorageObject, preserves client queue/status/error independently, allows partial success/retry/cancel, and makes counters/audit deterministic. A StorageObject may reference its batch item only through item FK; avoid duplicate bidirectional ownership.

One object may be referenced by exactly one domain file in MVP. Enforce in service layer and later DB nullable FK/unique strategy; do not allow a file record to point to `pending/failed/deleted` object. Shared model is preferred over duplicated document/media storage fields because it centralizes signing, cleanup, validation and audit.

## Project documents

`project_document_folders`: project FK, nullable parent FK self, name, description, creators/updater, `is_active`, `deleted_at`, timestamps. Unique active name among siblings requires PostgreSQL partial unique index on `(project_id, parent_id, lower(name)) WHERE deleted_at IS NULL`; document exact null-parent semantics in migration. Index `(project_id, parent_id, deleted_at)`.

`project_document_files`: project FK, folder FK, storage object FK, display name, description, tags JSON/text (MVP: optional simple JSON list), creators/updater, lifecycle/timestamps. Index `(project_id, folder_id, deleted_at)`, `(storage_object_id)` unique. Validate folder belongs to project.

`project_document_folder_permissions`: folder FK; `principal_type` check `user|role`; nullable `user_id`/`role_id` with XOR check; booleans view/upload/edit/delete/share; creator/timestamp. Unique `(folder_id, principal_type, user_id)` and equivalent role uniqueness (partial indexes), or normalize principal into two tables if migration portability is favored.

## Company media

`company_media_albums`: name, event date, description, optional cover storage object FK, creator, lifecycle/timestamps; active lower(name) unique if business wants it. No `parent_id`.

`company_media_files`: album FK, storage object FK, `media_type` check `image|video`, caption, taken_at, creator, lifecycle/timestamps. Unique storage object FK and index `(album_id, deleted_at, created_at)`.

`company_media_album_permissions`: same principal XOR design; flags view/upload/manage/delete, creator/timestamp. `manage` means album rename/archive and share; it does not bypass module permissions.

## Tree, move and lifecycle

Adjacency list is sufficient for expected internal tree depth: simple FK, cheap create, no path rewrite, and object key remains untouched. Move validates same project, active destination, no self/descendant destination, then updates only `parent_id`. Use a transaction with recursive CTE or bounded service traversal plus row locks to avoid concurrent cycle; add a defensive DB trigger only if concurrency evidence justifies it. Materialized path is deferred.

Archiving folder should make descendant folders/files unavailable in active browse even if their own flags are active; do **not** cascade physically by default. Restore requires ancestor policy: restore folder alone is allowed but remains invisible until ancestors restored, or explicitly require parent active—choose before implementation. No file versioning/recycle bin in MVP; archived metadata has retention before physical object cleanup.

## Migration impact

This proposal requires additive migrations and new relationships only after approval. It must not alter `ReportAttachment` or existing partner lifecycle tables. Backfill is intentionally out of scope; deployment should first create empty tables/indexes, then deploy code and run storage smoke tests against a non-production bucket.
