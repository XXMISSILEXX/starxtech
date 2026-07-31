# Phase 5 implementation report — Company Media cancel and database cleanup

## 1. Scope

Phase 5 adds safe cancellation of unfinished Company Media upload selections and
a database-only Flask CLI cleanup.  It preserves Phase 4's canonical
`(selection_session_id, client_file_id)` behavior, presign replay, metadata
conflict, complete replay, finalize replay, and post-commit derivative enqueue.

No S3/MinIO operation, orphan manifest, reconciliation export, scheduler,
cron, systemd unit, Celery schedule, browser persistence, resume, hash, or
multipart recovery was added.

## 2. Investigation summary

The pre-change findings are recorded in
[`PHASE5_INVESTIGATION.md`](PHASE5_INVESTIGATION.md).  The existing session
already supported `cancelled`, so Phase 5 reuses it.  It adds a nullable
`cleaned_at` timestamp to make cleanup replay stable and exclude previously
processed sessions from the periodic CLI.

## 3. Schema/status changes

Migration `20260731_0029_company_media_upload_cleanup` has parent
`20260730_0028` and is the single Alembic head.  It adds only:

```text
upload_selection_sessions.cleaned_at nullable timestamp
```

No Phase 4 migration was changed.  Session status remains `cancelled` after
cleanup; `completed`/`finalized` selections are immutable.  The downgrade
removes only the nullable timestamp.

## 4. Cancel API contract

```text
POST /company-media/albums/<album_id>/upload-sessions/<session_id>/cancel
```

The normal session owner, or `SUPER_ADMIN`/`ADMIN`, must also currently have
Company Media album upload authority.  CSRF applies through the existing
global CSRFProtect integration.  The album ID is checked against the session.

First cancellation example:

```json
{
  "ok": true,
  "session_id": 12,
  "status": "cancelled",
  "completed_files_preserved": 43,
  "pending_items_removed": 37,
  "pending_storage_objects_removed": 37,
  "protected_storage_objects_preserved": 0,
  "idempotent_replay": false
}
```

Replay returns `status: cancelled`, zero removal counters, current completed
count, and `idempotent_replay: true`.  Cancelled presign/finalize returns the
new, explicit `upload_session_cancelled` domain error.  A complete that loses
to cleanup returns its existing domain unavailable/not-found outcome, never a
500 or dangling media row.

The upload modal now exposes an in-progress Vietnamese action with confirmation:
“Hủy phần tải lên còn lại. Các tệp đã tải thành công vẫn được giữ.”  It disables
during the request and never uses localStorage/sessionStorage.

## 5. Cleanup CLI contract

```bash
# Safe default preview
flask cleanup-company-media-uploads --older-than-hours 48 --dry-run

# Apply database-only cleanup
flask cleanup-company-media-uploads --older-than-hours 48 --apply

# Bound a job or inspect one old session
flask cleanup-company-media-uploads --older-than-hours 48 --apply --limit 50
flask cleanup-company-media-uploads --older-than-hours 48 --apply --session-id 123
```

The default is dry-run; `--apply` is mandatory for writes.  It considers only
uncleaned Company Media album sessions that are not `completed`/`finalized`
and whose `expires_at` **or** `updated_at` is older than the cutoff.  Output is
structured counters for matched, processed, cleaned/replayed, removed items,
removed storage rows, and protected storage rows.  No periodic scheduler was
introduced.

## 6. Transaction and locking strategy

`app/company_media/upload_cleanup.py` is the one shared implementation used by
the route and CLI.  It creates an explicit nested all-or-nothing transaction
boundary, locks and refreshes the selection with `SELECT … FOR UPDATE`, locks
its direct Phase 4 items and candidate objects, flushes item removals before
object removals, deletes only empty batches, then marks the session cancelled
and cleaned.  The caller commits once after the service returns.  There is no
commit between individual cleanup operations and no network call in the
transaction.

Concurrent cancel/cleanup serializes on the session row.  If complete owns its
item/object lock first, it completes/activates and cleanup reloads then keeps
it.  If cleanup wins and deletes the pending item, complete returns a domain
availability error.  Finalize locks the same session and rejects cancellation
with `upload_session_cancelled` while preserving completed items.

## 7. Business-reference safety checks

An object is hard-deleted only if it is a non-deleted `pending` object solely
owned by cleanup-target unfinished items and has no surviving reference from:

- `UploadBatchItem`, `CompanyMediaFile`, `ProjectDocumentFile`, or
  `ReportAttachment`;
- `StorageDerivative`, `MediaProcessingJob`, or `DownloadEvent`;
- `User.avatar_storage_object`, company photo, partner profile photo, or
  `SystemSetting.brand_logo_storage_object`.

This intentionally fails closed.  Active, failed, uploaded, soft-deleted, or
otherwise uncertain objects are retained.  Completed upload items, active
objects, company media files, derivatives, and jobs are never deleted by Phase
5.

## 8. Race behavior

Two cancellers and two CLI workers are idempotent through the session lock and
`cleaned_at`.  The second caller sees a stable replay response.  Complete vs.
cancel is protected by the existing Phase 4 item/object locks plus forced
refresh; delete ordering prevents dangling `CompanyMediaFile` and storage
references.  PostgreSQL-specific tests for two cleanup workers and
complete-vs-cancel were added and are opt-in because SQLite cannot validate row
lock semantics.

## 9. Files changed

- `app/company_media/upload_cleanup.py` — shared database-only service.
- `app/company_media/routes.py` — cancel endpoint.
- `app/company_media/services.py`, `app/storage/services.py` — clear cancelled
  and unavailable domain behavior without changing Phase 4 successful contracts.
- `app/cli.py` — `cleanup-company-media-uploads` CLI.
- `app/models/storage.py` and migration `20260731_0029...` — `cleaned_at`.
- Company Media upload template/JS and JS test — minimal cancel UI.
- Phase 5 SQLite and PostgreSQL test modules plus investigation report.

## 10. Migration details

`20260731_0029` was upgraded on a disposable SQLite database, downgraded to
`20260730_0028`, then upgraded again successfully.  `flask db heads` and
`flask db current` on that disposable database both reported
`20260731_0029 (head)`.  The repository's default configured PostgreSQL was
not reachable, so it was not migrated.

## 11. Tests added

`tests/test_company_media_phase5_cleanup.py` covers pending-only cancellation,
mixed completed/pending preservation, business-reference preservation,
idempotent replay, owner/album/CSRF contract, clean-after-cancel complete
domain response, and CLI dry-run/apply/limit/session filtering.

`tests/test_company_media_phase5_postgresql.py` covers concurrent cleanup
workers and complete-vs-cancel using independent PostgreSQL connections.  It
requires `PHASE5_POSTGRES_URL` with the disposable Phase 4 database pattern
after migration upgrade.

## 12. Automated verification results

- `python -m compileall app` completed successfully.
- Focused Phase 5 + Phase 4 tests: **14 passed**.
- Phase 5/Phase 4 PostgreSQL tests: **3 skipped**, because neither
  `PHASE5_POSTGRES_URL` nor `PHASE4_POSTGRES_URL` was configured.
- `node --test tests_js/*.test.js`: **7 passed, 0 failed**.
- `pytest -q -rs` was run. The execution harness emitted progress markers but
  no final count/summary; no PASS count is claimed from that full-suite run.
- `git diff --check` completed without output/errors.
- Disposable SQLite CLI verification completed in dry-run and apply modes;
  both safely found zero rows on the empty verification database.

## 13. PostgreSQL concurrency verification

Not executed: no disposable PostgreSQL URL was available in this environment.
Run after migration on a disposable database:

```bash
PHASE5_POSTGRES_URL='postgresql+psycopg://starx_phase4:starx_phase4@127.0.0.1:55433/starx_phase4' \
pytest -vv tests/test_company_media_phase5_postgresql.py -rA
```

This is intentionally not substituted by SQLite results.

## 14. Manual smoke-test checklist

1. Start an upload containing both completed and still-pending files.
2. Choose the cancel action and confirm its Vietnamese warning.
3. Verify the completed files remain visible/downloadable and pending entries
   disappear from the database lifecycle only.
4. Repeat cancel and verify the replay response is successful with zero removals.
5. Try another user, a wrong album ID, no CSRF token, and a viewer-admin; each
   must be denied.
6. Run CLI dry-run, review counters, then run `--apply` on a disposable DB.
7. In two browser/API workers, race complete with cancel and two cancels;
   confirm only completed media survives and no request returns 500.

## 15. Known limitations

Phase 5 deliberately leaves raw pending object bytes in S3-compatible storage.
The database is the source of truth for a later, separate allowlist-based S3
reconciliation process.  Cleanup is conservative: a suspicious reference can
leave an unreferenced pending DB object rather than risk business data.

## 16. Explicit out of scope

No S3 HEAD/LIST/DELETE, no orphan manifest, no reconciliation/export, no cron,
systemd or Celery scheduler, no resume/recovery, no hashing, no multipart
recovery, no single-file cancellation, no restoration of cancelled sessions,
no completed-file rollback, and no Project Documents/Daily Reports behavior
change was implemented.

## 17. Rollback notes

The migration is additive.  Prefer rolling back application code while
retaining `cleaned_at`; do not downgrade a production database without a
separate migration/backup plan.  A cleanup transaction rolls back on an
unexpected database error, and no active/completed business row is selected for
deletion by the service.
