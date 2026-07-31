# Schema and constraint audit

| Table/model | Key columns/state | Relationships / constraints |
| --- | --- | --- |
| `upload_selection_sessions` | PK; actor; module/target; declared/presigned counters; status; `expires_at` | batches via `UploadBatch.selection_session_id`; owner/expiry and target/status/expiry indexes; checks. `app/models/storage.py:68-84`. |
| `upload_batches` | PK; nullable session FK; count counters; status | item ORM cascade delete-orphan; item DB FK cascades on batch delete; target/creator/status indexes. `app/models/storage.py:41-66`. |
| `upload_batch_items` | PK; batch FK; nullable object FK; non-null client ID/name/MIME/size/status | current unique is `(upload_batch_id, client_file_id)` only; batch FK `ON DELETE CASCADE`. `app/models/storage.py:99-124`. |
| `storage_objects` | PK; bucket/key/metadata/uploader; upload/processing status | unique `(bucket, object_key)`; one object may be linked to many batch items by schema. `app/models/storage.py:8-39`. |
| `company_media_files` | PK; album FK RESTRICT; non-null object FK | unique `storage_object_id`: one storage object → at most one CompanyMediaFile. `app/models/company_media.py:25-39`. |

There is no local item `selection_session_id` and no equivalent `UNIQUE(selection_session_id, client_file_id)`. Session association is indirect through `upload_batches` (`migrations/versions/20260722_0017_strict_storage_policy.py:15-18`), which cannot support a cross-table unique constraint.

## Minimum proposal

Add nullable `upload_batch_items.selection_session_id` FK to `upload_selection_sessions`, backfill from parent batch where present, then add:

```sql
ALTER TABLE upload_batch_items
  ADD CONSTRAINT uq_upload_batch_items_selection_client_file
  UNIQUE (selection_session_id, client_file_id);
```

The name follows current `uq_<table>_<columns>` convention (`20260720_0010_add_storage_batch_foundation.py:54-56`, `20260725_0026_daily_report_create_idempotency.py:16-21`). PostgreSQL allows multiple NULLs, preserving legacy/non-session items. Populate it for new Phase 4 Company Media items. No second complete constraint is needed: `uq_company_media_files_storage_object` already guarantees one media file per storage object.

## Read-only duplicate preflight SQL

Do not execute this on production during this audit. Before migration, require zero results; do not delete, select a canonical row, alter key, or touch S3.

```sql
-- 1. Future session/client-key collisions.
SELECT b.selection_session_id, i.client_file_id, COUNT(*) AS row_count,
       array_agg(i.id ORDER BY i.id) AS item_ids
FROM upload_batch_items AS i
JOIN upload_batches AS b ON b.id = i.upload_batch_id
WHERE b.selection_session_id IS NOT NULL
GROUP BY b.selection_session_id, i.client_file_id
HAVING COUNT(*) > 1;

-- 2. Existing one-object-to-many-media drift (should be zero).
SELECT storage_object_id, COUNT(*) AS row_count,
       array_agg(id ORDER BY id) AS company_media_file_ids
FROM company_media_files
GROUP BY storage_object_id
HAVING COUNT(*) > 1;

-- 3. Pending accepted/uploading item with missing/NULL object.
SELECT i.id AS upload_batch_item_id, i.status, i.storage_object_id
FROM upload_batch_items AS i
LEFT JOIN storage_objects AS o ON o.id = i.storage_object_id
WHERE i.status IN ('accepted','uploading')
  AND (i.storage_object_id IS NULL OR o.id IS NULL);

-- 4. Invalid current client IDs.
SELECT id, upload_batch_id, client_file_id
FROM upload_batch_items
WHERE client_file_id IS NULL OR btrim(client_file_id) = ''
   OR length(client_file_id) > 255;
```

An item has one scalar `storage_object_id`; therefore “one pending item has many StorageObjects” is structurally impossible. Query 3 is the appropriate integrity check. Query 2 is both the requested accidental-reuse check and the existing-schema duplicate check; the schema has no purpose column to distinguish intent further.
