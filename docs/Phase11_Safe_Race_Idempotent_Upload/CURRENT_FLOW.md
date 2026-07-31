# Current Company Media upload flow

## Verified sequence

```mermaid
sequenceDiagram
  participant B as Browser JS
  participant R as Company Media routes
  participant S as storage.services
  participant DB as PostgreSQL / SQLAlchemy
  participant O as S3-compatible storage
  participant W as media worker
  B->>R: POST selection session {file_count,total_size_bytes}
  R->>S: create_upload_selection_session
  S->>DB: INSERT upload_selection_sessions; COMMIT
  B->>R: POST presign batch {session_id, client_file_id, filename, MIME, size}
  R->>S: create_upload_batch_presign
  S->>DB: INSERT batch, object, item; counters++; COMMIT
  S->>O: create presigned POST policy before DB commit
  S-->>B: item id + URL/fields
  B->>O: multipart POST file
  B->>R: POST complete {upload_batch_item_id}
  R->>S: HEAD then mark object active/item completed; COMMIT
  R->>DB: create CompanyMediaFile if absent; COMMIT
  R->>W: enqueue derivatives only if media newly created
  B->>R: POST finalize
  R->>S: mark session completed; COMMIT
```

## Step-by-step evidence

1. A queue entry is made in browser memory with `clientFileId: newId()`. `newId()` uses `crypto.randomUUID()` or timestamp/`Math.random()` fallback (`app/static/js/company-media-upload.js:148,283`). There is no persistence.
2. `prepare()` posts valid queue count and `File.size` sum to the selection endpoint (`company-media-upload.js:262-264`); route calls `create_upload_selection_session` (`app/company_media/routes.py:112-118`).
3. The service validates selection limits, writes declared count/bytes and naïve UTC expiry, then commits (`app/storage/services.py:20-47`). Columns are at `app/models/storage.py:68-84`.
4. Browser sends `selection_session_id`, `client_file_id`, filename, MIME and size (`company-media-upload.js:265-270`). Route authorizes album upload then delegates (`app/company_media/routes.py:97-111`).
5. Presign validates batch limits, request-local client IDs, metadata, declared counters, and active-storage capacity (`app/storage/services.py:76-164`; `app/storage/validation.py:26-68`).
6. It creates/flushed `UploadBatch`, then per accepted file generates a UUID opaque key, creates/flushed pending `StorageObject`, creates/flushed accepted `UploadBatchItem`, and calls the signer (`app/storage/services.py:166-196`). Key building: `app/storage/keys.py:50-64`. S3 provider creates a multipart POST policy (`app/storage/providers.py:91-114`); browser sends FormData POST (`company-media-upload.js:249-254`).
7. It increments `presigned_files` and `presigned_size_bytes` and commits (`app/storage/services.py:205-209`). There is no per-user reservation or quota ledger.
8. Browser direct-POST retry preserves `entry.presign` (up to three attempts), then posts item ID to complete (`company-media-upload.js:256-261`). Complete owner-checks, HEAD-verifies exact size/MIME/checksum, sets object active/item completed, refreshes batch, and commits (`app/storage/services.py:227-258,292-313`).
9. Company Media calls generic complete, finds/creates `CompanyMediaFile`, commits separately, then enqueue helper runs only on creation (`app/company_media/services.py:165-178`). Enqueue creates/commits a job then dispatches after that commit (`app/media_processing/services.py:96-111`).
10. Finalize loads a pending session, validates failed IDs, marks selected accepted/uploading items failed, requires no unfinished items, sets session `completed`, and commits (`app/storage/services.py:49-74,211-224`). It creates no media and changes no storage quota.

## States, quota, expiry, authorization

`StorageObject` is pending → active (or remains pending while item fails HEAD); item is accepted → completed/failed; batch reaches uploading/completed/partial_failed/failed; session moves pending → completed. Model states/constraints are in `app/models/storage.py:8-124`.

Storage usage is calculated from active originals, non-deleted derivatives and live ZIPs. Pending objects and selection declarations do not consume it (`app/storage/quota.py:6-24`). Upload-side persisted accounting is only session presign counters.

`_selection_session` checks actor/module/target, pending state and expiry only for presign/finalize (`app/storage/services.py:211-224`). Complete checks owner/admin but does not recheck the selection session (`:227-238,328-335`). Routes authorize album upload before all three operations (`app/company_media/routes.py:99-100,114-115,129-130`).
