# Proposed Phase 4 scope

## Must implement

- Race-safe database unique constraint for `(selection_session_id, client_file_id)` after the actual local schema relation is added.
- Presign create-or-replay, canonical metadata conflict HTTP 409, same item/object/key, and selection counters exactly once.
- Complete idempotency including concurrent CompanyMediaFile get-or-create and derivative enqueue only once.
- Finalize idempotency with terminal result replay.
- Presign expiry HTTP 410; never automatic new selection session.
- Minimal frontend behavior: retain current selection ID, understand replay/conflict/expiry, do not discard usable item/session ID.
- SQLite/FakeStorage, PostgreSQL concurrency, browser, migration, and regression tests.

## Explicitly excluded

- Cancel endpoint/UI.
- S3 orphan/pending cleanup, cleanup cron/systemd timer, or changes to generic cleanup.
- Resume after reload/localStorage persistence, full-file hash, multipart resume, cross-device recovery, content deduplication.
- Automatic session after expiry, advanced reconciliation, and Project Documents/Daily Report behavior changes except shared-code regression safety.

## Open decisions requiring approval

1. **Complete after expiry:** current complete permits it because it checks item ownership, not selection expiry. Decide whether accepted items get explicit bounded completion/finalization grace or expiry rejects them; no grace is assumed.
2. **Failed item retry:** decide same canonical key/object versus explicit replacement/new selection. Current HEAD failure terminally marks item failed.
3. **Second unique constraint:** audit says no: existing `uq_company_media_files_storage_object` is sufficient for one media record/object.
4. **Reservation release:** no DB reservation ledger exists. Session counters never release on expiry; generic pending cleanup exists (`app/storage/services.py:273-289`) but is explicitly out of Phase 4. Approve this accepted risk or widen future scope.
