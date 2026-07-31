# Findings

Severity is implementation priority, not a claim of external compromise.

## F-001 — Presign is non-idempotent at selection-session scope

- Severity: High; status: confirmed.
- Evidence: `create_upload_batch_presign` unconditionally creates `UploadBatch` (`app/storage/services.py:166-168`) then a UUID key, `StorageObject`, and `UploadBatchItem` for each accepted input (`:170-196`). The sole item uniqueness is `UNIQUE(upload_batch_id, client_file_id)` (`app/models/storage.py:99-112`).
- Impact: identical session/client-ID requests can create a second batch, pending object, item, and key. No old-item query exists.
- Verification: static trace; current tests do not cover sequential/concurrent presign replay.
- Recommendation: session-level uniqueness plus create-or-replay.

## F-002 — Session counters duplicate with duplicate presigns

- Severity: High; status: confirmed.
- Evidence: validation compares incoming accepted metadata to current counters (`app/storage/services.py:134-151`), then adds `batch.accepted_files` and linked-object sizes (`:205-208`).
- Impact: a replay while declared capacity remains increments `presigned_files`/`presigned_size_bytes` again. When the first request exhausted the exact declaration, the replay is rejected by quota; that is not idempotency.
- Recommendation: increment only for winning canonical inserts; replay counters never change.

## F-003 — Concurrent presign has no database race barrier

- Severity: High; status: confirmed for missing barrier; PostgreSQL interleaving result needs integration verification.
- Evidence: selection is loaded with `db.session.get`, never locked (`app/storage/services.py:118,211-224`); shared service has no `IntegrityError`, savepoint, `with_for_update`, or upsert.
- Impact: A/B can both read capacity then insert differently keyed rows because batch IDs differ. ORM counter increments may also lose updates.
- Recommendation: database unique key plus conflict/replay recovery; test PostgreSQL concurrency.

## F-004 — Retry path discards the selection session

- Severity: High; status: confirmed.
- Evidence: direct S3 retry retains `entry.presign` (`app/static/js/company-media-upload.js:256-259`), but “retry failed” clears item/presign/session IDs then calls `upload(failed)` (`:290`); `prepare()` always creates a new session (`:262-273`).
- Impact: a timeout after accepted presign or successful complete can create a new selection/object even with the same queue client ID.
- Recommendation: retry same usable session/item; never create session automatically after expiry.

## F-005 — Complete is sequentially idempotent, not concurrency-hardened

- Severity: Medium; status: confirmed sequential, probable concurrent response failure.
- Evidence: generic complete returns `idempotent:true` when active/completed (`app/storage/services.py:227-236`); existing test calls it twice and observes one enqueue (`tests/test_company_media_permissions_ux.py:221-224`). `CompanyMediaFile.storage_object_id` is unique (`app/models/company_media.py:25-39`), but service does query-then-insert with no conflict handling (`app/company_media/services.py:165-177`).
- Impact: sequential calls yield one media file/job. Concurrent calls can both HEAD and one database insert can raise unhandled `IntegrityError`/500, although the unique constraint prevents a second row.
- Recommendation: conflict-safe media get-or-create and replay success after authorization.

## F-006 — Finalize is not idempotent

- Severity: Medium; status: confirmed.
- Evidence: first call sets session `completed` (`app/storage/services.py:66-68`); loader permits only `pending` (`:219-223`).
- Impact: timeout after successful finalize produces 410 on retry rather than terminal result.
- Recommendation: terminal replay must return persisted counts/status without mutation.

## F-007 — Expiry differs by endpoint

- Severity: Medium; status: confirmed.
- Evidence: TTL/naïve UTC at `app/storage/services.py:39,46`; presign sends structured 410 (`:219-223`; `tests/test_company_media_upload_limits.py:264-279`). Complete does not load session; finalize does.
- Impact: an object can complete and create visible media after expiry, then finalize 410. No server automatic session creation exists; frontend retry creates a new selection.
- Recommendation: approve explicit accepted-item completion/finalization policy; do not add broad grace by assumption.

## F-008 — Client ID is queue-local and weakly validated

- Severity: Medium; status: confirmed.
- Evidence: UUID/fallback at `company-media-upload.js:148`, allocation at `:283`, request nonempty/unique check at `app/storage/services.py:121-123`, DB `String(255) NOT NULL` at `app/models/storage.py:109-112`.
- Impact: reload/remove-readd gets a new ID; fallback has no strict UUID guarantee; same ID in another batch is valid.
- Recommendation: preserve opaque ID only in active selection and apply compatible length/format policy.

## F-009 — Migration needs preflight; second media constraint is redundant

- Severity: Medium; status: confirmed.
- Evidence: current head `20260729_0027` (`migrations/versions/20260729_0027_add_user_ui_preferences.py:3-17`); existing named unique media constraint in `20260721_0013_add_company_media_core.py:14`.
- Impact: new session/client constraint can fail on history; extra media constraint would duplicate existing protection.
- Recommendation: preflight/fail-fast, no automatic row/object remediation.
