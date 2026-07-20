# Data Model chi tiết

## 1. StorageObject

Dùng chung cho Project Documents và Company Media.

```text
storage_objects
- id
- bucket
- object_key
- thumbnail_object_key nullable compatibility only
- original_filename
- mime_type
- file_ext
- file_size
- checksum_sha256 nullable
- width nullable
- height nullable
- duration_seconds nullable
- uploaded_by_id FK users
- upload_status enum: pending | active | failed | deleted
- processing_status enum: none | queued | processing | completed | failed
- created_at
- completed_at nullable
- deleted_at nullable
```

Indexes/constraints:

```text
unique(bucket, object_key)
index(upload_status, created_at)
index(processing_status, created_at)
index(uploaded_by_id, upload_status)
```

Rules:

- `object_key` immutable after issuance.
- Client never chooses key.
- `original_filename` is display metadata only.
- No domain file may reference pending/failed/deleted object.

## 2. StorageDerivative

Canonical place for thumbnail/preview/poster.

```text
storage_derivatives
- id
- storage_object_id FK storage_objects
- derivative_type enum: thumbnail | preview | poster | video_preview
- bucket
- object_key
- mime_type
- file_ext
- file_size
- width nullable
- height nullable
- duration_seconds nullable
- created_by_job_id nullable FK media_processing_jobs
- created_at
- deleted_at nullable
```

Constraints:

```text
unique active(storage_object_id, derivative_type)
unique(bucket, object_key)
index(storage_object_id, derivative_type)
```

Derivative types:

```text
thumbnail: small grid/card image
preview: larger image for lightbox
poster: video poster frame
video_preview: reserved, not MVP
```

## 3. MediaProcessingJob

Durable job state in DB.

```text
media_processing_jobs
- id
- storage_object_id FK storage_objects
- job_type enum: image_derivatives | video_derivatives
- status enum: pending | processing | succeeded | failed | cancelled
- celery_task_id nullable
- attempts
- max_attempts
- started_at nullable
- finished_at nullable
- error_code nullable
- error_message nullable
- created_at
- updated_at
```

Rules:

- PostgreSQL is authoritative.
- Celery duplicate task must be idempotent.
- One active job per `(storage_object_id, job_type)`.
- Worker skips inactive/deleted/failed StorageObject.

## 4. UploadBatch

Tracks a user-visible batch.

```text
upload_batches
- id
- module_type enum: project_documents | company_media
- target_type enum: folder | album
- target_id
- created_by_id FK users
- total_files
- accepted_files
- completed_files
- failed_files
- status enum: pending | uploading | completed | partial_failed | failed
- created_at
- completed_at nullable
```

## 5. UploadBatchItem

Tracks each client file including rejected files.

```text
upload_batch_items
- id
- upload_batch_id FK upload_batches
- storage_object_id nullable FK storage_objects
- client_file_id
- original_filename
- mime_type
- file_size
- status enum: accepted | rejected | uploading | completed | failed | cancelled
- error_message nullable
- created_at
- updated_at
```

Constraints:

```text
unique(upload_batch_id, client_file_id)
```

Why needed:

- Rejected files have no StorageObject.
- Retry/cancel/partial failure tracking.
- Upload UI state mirrors server state.
- Audit/counters deterministic.

## 6. ProjectDocumentFolder

```text
project_document_folders
- id
- project_id FK projects
- parent_id nullable self FK
- name
- description nullable
- created_by_id FK users
- updated_by_id nullable FK users
- is_active
- deleted_at nullable
- created_at
- updated_at
```

Indexes/constraints:

```text
index(project_id, parent_id, deleted_at)
unique active sibling name: project_id + parent_id + lower(name) WHERE deleted_at IS NULL
```

Rules:

- Adjacency list.
- Move validates no self/descendant.
- Rename/move does not touch StorageObject key.

## 7. ProjectDocumentFile

```text
project_document_files
- id
- project_id FK projects
- folder_id FK project_document_folders
- storage_object_id FK storage_objects unique
- display_name
- description nullable
- tags JSON/text nullable
- created_by_id FK users
- updated_by_id nullable FK users
- is_active
- deleted_at nullable
- created_at
- updated_at
```

## 8. ProjectDocumentFolderPermission

```text
project_document_folder_permissions
- id
- folder_id FK project_document_folders
- principal_type enum: user | role
- user_id nullable FK users
- role_id nullable FK roles
- can_view
- can_upload
- can_edit
- can_delete
- can_share
- created_by_id FK users
- created_at
```

Rule:

- user_id XOR role_id.
- No explicit deny.

## 9. CompanyMediaAlbum

```text
company_media_albums
- id
- name
- event_date nullable
- description nullable
- cover_storage_object_id nullable FK storage_objects
- created_by_id FK users
- is_active
- deleted_at nullable
- created_at
- updated_at
```

No parent_id.

## 10. CompanyMediaFile

```text
company_media_files
- id
- album_id FK company_media_albums
- storage_object_id FK storage_objects unique
- media_type enum: image | video
- caption nullable
- taken_at nullable
- created_by_id FK users
- is_active
- deleted_at nullable
- created_at
- updated_at
```

## 11. CompanyMediaAlbumPermission

```text
company_media_album_permissions
- id
- album_id FK company_media_albums
- principal_type enum: user | role
- user_id nullable FK users
- role_id nullable FK roles
- can_view
- can_upload
- can_manage
- can_delete
- created_by_id FK users
- created_at
```

## Migration strategy

- Additive migrations only.
- No modification to ReportAttachment.
- No modification to Partner lifecycle tables.
- Create storage/batch tables first.
- Add worker tables in Phase 2.
- Add module domain tables in Phase 3/5.
