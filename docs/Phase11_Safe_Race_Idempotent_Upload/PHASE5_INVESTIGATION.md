# Phase 5 investigation — cancel and database-only cleanup for Company Media uploads

## Scope and audit boundary

This investigation was completed before Phase 5 code changes.  It covers the
Company Media direct-upload lifecycle after Phase 4, its shared storage models,
the existing Daily Report cleanup implementation, all `StorageObject` foreign
keys, the Phase 4 migration, and its SQLite/PostgreSQL tests.  Phase 5 must
not call S3, create an orphan manifest, or schedule any worker.

## Current schema and status machine

| Model/table | Relevant columns and relations | Statuses |
| --- | --- | --- |
| `UploadSelectionSession` / `upload_selection_sessions` | actor, module/target, declared and presigned counters, expiry; batches through `UploadBatch.selection_session_id`; Phase 4 items also have a direct selection FK | `pending`, `uploading`, `ready`, `completed`, `finalized`, `cancelled`, `expired` |
| `UploadBatch` / `upload_batches` | nullable selection FK; `items` ORM delete-orphan and item DB FK `ON DELETE CASCADE` | `pending`, `uploading`, `completed`, `partial_failed`, `failed` |
| `UploadBatchItem` / `upload_batch_items` | batch FK `ON DELETE CASCADE`; nullable direct selection FK (Phase 4); nullable storage-object FK; canonical unique `(selection_session_id, client_file_id)` | `accepted`, `rejected`, `uploading`, `completed`, `failed`, `cancelled` |
| `StorageObject` / `storage_objects` | bucket/key unique; `batch_items`; soft-delete timestamp | upload: `pending`, `uploaded`, `active`, `failed`, `deleted`; processing: `none`, `queued`, `processing`, `completed`, `failed` |
| `CompanyMediaFile` / `company_media_files` | non-null `storage_object_id`, unique; album FK `RESTRICT` | active/archive state is `is_active` plus `deleted_at` |
| `StorageDerivative` / `storage_derivatives` | non-null `storage_object_id` FK, soft-delete timestamp | derivative type only |
| `MediaProcessingJob` / `media_processing_jobs` | non-null `storage_object_id` FK | `pending`, `processing`, `succeeded`, `failed`, `cancelled` |

`20260730_0028_company_media_selection_item_idempotency` is the current Phase
4 migration head.  It added `upload_batch_items.selection_session_id`, its FK,
index, and canonical unique constraint.  It must not be modified.

## Reference graph and delete safety

```text
UploadSelectionSession
  ├─ UploadBatch ──< UploadBatchItem >── StorageObject
  └─ (Phase 4 direct) UploadBatchItem

StorageObject ── CompanyMediaFile / ProjectDocumentFile / ReportAttachment
              ── StorageDerivative / MediaProcessingJob / DownloadEvent
              ── User.avatar / Company.company_photo / Partner.profile_photo
              ── SystemSetting.brand_logo
```

The database has restrictive/default FKs for most of these relationships.
Phase 5 must therefore not delete derivative/job/audit rows as a side effect.
It deletes a storage row only when all of the following are true:

1. it is `upload_status == 'pending'`, is not soft deleted, and is not active;
2. it has no `CompanyMediaFile`, `ProjectDocumentFile`, `ReportAttachment`,
   `StorageDerivative`, `MediaProcessingJob`, `DownloadEvent`, display-image,
   or any surviving `UploadBatchItem` reference; and
3. it belongs solely to a non-completed Company Media item selected for this
   cleanup.

`completed` items, their active objects, all `CompanyMediaFile` rows, active
objects, all storage rows with a business/reference edge, and all derivatives
and jobs are absolute keep rows.  A strange/stale status never overrides a
business reference.  A pending object that cannot be proven disposable is
retained; its unfinished item can still be removed safely.

## Phase 4 complete/finalize flow

`complete_upload_item` locks and forcibly refreshes the item then object with
`SELECT … FOR UPDATE`, verifies storage with a HEAD call only when not already
completed, changes the object to `active` and the item to `completed`, invokes
the Company Media completion handler in the same DB commit, and returns an
idempotent replay for active/completed rows.  The handler creates one
`CompanyMediaFile` behind its unique storage-object constraint; derivative
enqueue happens only after that commit and only for the creating request.

Company Media finalization locks the selection session, keeps the historical
terminal `completed` status, and returns persisted counts on replay.  It never
creates media.  Accepted items may complete after expiry by the existing Phase
4 policy.  Existing generic pending-object cleanup and the Daily Report cleanup
call S3 and are separate/out of scope for Phase 5.

## Permissions

All Company Media routes first require authenticated module access.  The album
route additionally uses `upload_album`, which denies `VIEWER_ADMIN` writes and
enforces module RBAC plus the album ACL.  The session owner is the normal
actor; `SUPER_ADMIN`/`ADMIN` may perform equivalent upload work.  Phase 5 will
use the same album upload permission and require owner-or-admin for a specific
selection session.  CSRFProtect already applies to POST JSON routes.

## Proposed transaction and locking model

The shared service starts one database transaction, locks the selection with
`SELECT … FOR UPDATE`, reloads it with `populate_existing`, then locks its
direct Phase 4 items and candidate storage objects.  It classifies completed
items before any deletion.  It flushes item deletion before deleting proven
unreferenced pending objects, deletes only empty session batches, marks the
session `cancelled`, and records a cleanup timestamp.  There is no commit in
the service and no network call.

This ordering resolves races as follows:

- If complete owns an item/object lock first, it activates/completes and creates
  media before cleanup obtains item locks; cleanup reloads and keeps it.
- If cleanup commits first, complete re-reads no item and returns the explicit
  `upload_item_not_available` domain contract, never activating a missing row.
- Concurrent cancel/cleanup serializes on the selection lock.  The winner
  cleans; the follower observes `cleaned_at` and returns idempotent success.
- Finalize serializes on the same selection lock.  After cancellation it
  returns `upload_session_cancelled`; completed items remain intact.

The complete path must not acquire the selection lock: that avoids a reverse
lock order (`item → session`) and preserves Phase 4's narrow lock design.

## Migration decision

A small additive migration is required for nullable `cleaned_at` on
`upload_selection_sessions`.  Existing `cancelled` status is reused; no new
enum/check value is necessary.  The migration parent will be `20260730_0028`.
Downgrade drops only the nullable column.  The column permits a stable replay
response and prevents the periodic command from repeatedly selecting a session
whose incomplete items have already been removed.

## Proposed API and CLI contracts

API:

```text
POST /company-media/albums/<album_id>/upload-sessions/<session_id>/cancel
```

The authenticated owner or an admin with album upload authority receives:

```json
{"ok":true,"status":"cancelled","completed_files_preserved":43,
 "pending_items_removed":37,"pending_storage_objects_removed":37,
 "idempotent_replay":false}
```

Repeat calls return the same status, zero removal counts, current preserved
completed count, and `idempotent_replay: true`.  Wrong album/session, missing
CSRF, unauthenticated, insufficient album permission, and non-owner are
rejected.  A completed selection is immutable and cannot be cancelled.

CLI:

```text
flask cleanup-company-media-uploads --older-than-hours N [--dry-run|--apply]
  [--limit N] [--session-id ID]
```

Dry-run is the default.  Candidates are Company Media album sessions that are
not terminally completed/finalized or already cleaned and whose `expires_at`
or `updated_at` is older than the threshold; `expires_at` expresses the
upload-lifecycle deadline while `updated_at` catches abandoned sessions whose
expiry was extended.  `--session-id` narrows to one eligible Company Media
session.  Each apply invocation uses the same locking service and emits a
structured count summary.  No scheduler is added.

## Test plan

Tests will cover pending-only and mixed cancellation, preservation of
completed/media/active/referenced objects, idempotent replay, owner/album/CSRF
denials, dry-run/apply/threshold/limit/session CLI behavior, no storage-provider
or derivative enqueue call, Phase 4 regression, and PostgreSQL races for
complete-vs-cancel plus two cleanup workers.  PostgreSQL tests will use the
Phase 4 disposable URL pattern; SQLite is not evidence for row locks.

## Risks and rollback

The known operational limitation is deliberate: because Phase 5 never calls
S3, pending keys may remain in object storage until a later allowlist-based
reconciliation phase.  Database safety wins over reclaiming every row: any
uncertain reference retains the object.  The only migration is additive, so
code rollback should retain it; do not downgrade production without a separate
release plan.  If an unexpected FK/reference blocks cleanup, the transaction
rolls back without deleting active/completed business data.
