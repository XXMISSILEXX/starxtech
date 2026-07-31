# Phase 4 implementation report — Safe race-idempotent Company Media upload

## Scope and safety result

Implemented locally only. No production database, bucket, deployment, commit or
push was used. The solution is intentionally limited to Company Media; Project
Documents and Daily Reports retain their existing workflow except for the shared
complete-item lock/refresh behavior required for safe concurrency.

## Verified schema and migration

Before editing, the audited schema was confirmed in `app/models/storage.py` and
`app/models/company_media.py`:

| Entity | Table | Phase 4 relation/invariant |
| --- | --- | --- |
| Selection session | `upload_selection_sessions` | actor/module/target, declared and presigned counters, expiry/status |
| Upload batch | `upload_batches` | request grouping; indirect session relation remains |
| Upload item | `upload_batch_items` | now has direct nullable `selection_session_id` |
| Storage object | `storage_objects` | one item references one object scalar; unique bucket/key remains |
| Company media | `company_media_files` | existing unique `uq_company_media_files_storage_object` provides one media/object |

`client_file_id` remains `String(255)`, non-null. New Company Media selection
requests require a nonblank ASCII identifier containing only alphanumerics and
`._:-`; the Phase 3A generated UUID-style value remains valid.

Migration `20260730_0028_company_media_selection_item_idempotency`, parent
`20260729_0027`, adds direct FK
`fk_upload_batch_items_selection_session`, index
`ix_upload_batch_items_selection_session_id`, and constraint
`uq_upload_batch_items_selection_client_file`. It relationally backfills only
from the owning batch and preserves NULL legacy rows. No second CompanyMediaFile
constraint was added because `uq_company_media_files_storage_object` already
exists.

## Duplicate preflight

Added read-only CLI command:

```bash
flask company-media-upload-preflight
```

It reports canonical key duplicates, invalid client IDs, accidentally shared
media objects, and pending/uploading items without a storage object; any result
fails non-zero and requires manual review. It never deletes rows, selects a
canonical record, changes keys, or touches S3. The migration repeats the
critical duplicate/invalid/media checks and fails closed before adding the
constraint.

Disposable SQLite and PostgreSQL preflight results were all zero. Production
has not been queried and must run this command before rollout.

## Presign create-or-replay and metadata

For a Company Media selection session, authorization, target scope, expiry and
Phase 2 limits run before replay. Metadata goes through one helper using the
existing validator: trimmed filename with normalized extension, canonical MIME,
exact size, and existing image/video category policy. Same key with any changed
canonical filename, MIME or size returns HTTP 409:

```json
{"ok":false,"error":{"code":"idempotency_conflict","message":"Mã tệp đã được sử dụng cho một tệp khác.","details":{},"retryable":false}}
```

For a new key, the code locks the selection for counter serialization, creates
the pending `StorageObject` and direct-session `UploadBatchItem` in a savepoint,
and flushes before commit. A unique violation rolls back only that savepoint,
queries the canonical winner and replays it. The signer is called only after a
canonical object has committed. Pending replay returns a new usable signed
contract for the same object key. Completed replay returns `status: completed`
without a new upload contract. Failed items return non-retryable
`upload_item_not_retryable`, requiring a new selection.

`idempotent_replay` and `status` were added without renaming legacy accepted
fields. New winners alone increment `selection.presigned_files`,
`selection.presigned_size_bytes`, and batch accepted counters; replays,
conflicts and race losers do not.

## Complete, finalize and expiry

`complete_upload_item` locks and forcibly refreshes the canonical item and
object (`SELECT … FOR UPDATE` on PostgreSQL) before inspecting state. This
forced refresh is important: a waiting ORM session must not evaluate stale
pre-lock state. Completed/active requests skip HEAD and return successful
`idempotent_replay`. Company Media media creation occurs in the same commit as
activation; the existing storage-object unique constraint plus nested
IntegrityError recovery ensures one `CompanyMediaFile`, and derivative enqueue
happens only for the committed creator.

Finalize locks the selection. Its persisted terminal state remains the existing
`completed` status for backward compatibility. Repeating finalize returns the
same counts with `idempotent_replay: true` and no mutations. New presign after
expiry returns 410 `selection_session_expired` and creates no batch/item/object
or counter increment. An already-issued item may still complete after expiry;
then finalize succeeds only when every relevant item is terminal. No new session
is ever created automatically.

## Frontend and asset version

`company-media-upload.js` retains `clientFileId` and selection ID across the
current-page retry. Retry re-presigns the same canonical item; a replay marked
`completed` is shown as success and is not posted to storage again. Conflict and
expiry messages are safe Vietnamese messages; 410 stops the flow rather than
creating another selection. No browser persistence was added. Static asset
version changed once to `20260730-8404`.

## Verification evidence

| Check | Result |
| --- | --- |
| Python compile | `python -m compileall app` passed |
| Phase 4 SQLite/FakeStorage tests | 7 passed in `tests/test_company_media_phase4_idempotency.py` |
| Existing Company Media/storage targeted tests | passed after partial-acceptance compatibility fix |
| PostgreSQL migration | PostgreSQL 16.11 disposable DB upgraded to `20260730_0028` |
| Migration downgrade/upgrade | downgraded to `20260729_0027`, re-upgraded; named constraint verified |
| PostgreSQL concurrent presign + complete | 1 passed: two simultaneous requests ended with one item, one object, counters `(1, 5)`, one media and one enqueue |
| Duplicate preflight | clean on disposable SQLite and PostgreSQL |

The PostgreSQL test command was:

```bash
PHASE4_POSTGRES_URL=postgresql+psycopg://…@127.0.0.1:55433/starx_phase4 \
  pytest -q tests/test_company_media_phase4_postgresql.py -rA
```

The actual disposable database was `starx_phase4` in local Docker PostgreSQL
16.11 at `127.0.0.1:55433`; no production endpoint was used. Full-suite and
manual S3-dev checks remain required before release.

## Rollout, rollback and remaining manual checks

1. Back up production PostgreSQL.
2. Run `flask company-media-upload-preflight` read-only. Stop for any nonzero result and review manually.
3. Apply the additive migration and verify the named constraint.
4. Release backend and versioned frontend together.
5. Smoke-test normal/replay/conflict/complete/finalize flows using only S3 dev.
6. Observe structured outcomes without logging signed URLs, object keys, buckets, credentials or raw conflicting metadata.
7. On code incident, rollback code if needed while retaining the additive constraint when compatible; do not downgrade production schema without a separate plan.

Still manual: real S3-dev POST/HEAD with an expired signed policy, 3–5 ordinary
images, two browser tabs, and Phase 1/2/3A plus Project Documents/Daily Report
release regression in the target environment.

## Explicit exclusions

No cancel endpoint/UI, S3 orphan cleanup, cleanup scheduler, resume after
reload, localStorage/sessionStorage, hashing, multipart recovery, content
deduplication, cross-device recovery, automatic session creation, advanced
failed-item recovery, UI redesign, deploy, commit or push was implemented.
