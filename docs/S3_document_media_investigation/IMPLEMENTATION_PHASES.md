# Implementation phases

No phase begins until its approvals, threat review and environment credentials are separately authorized. This investigation performs none of these changes.

## Phase 1 — Storage foundation + batch presign contract

Add config contract (bucket/endpoint/region only via env/secrets), provider interface/fake provider, `StorageObject`, approved `UploadBatch`/`UploadBatchItem`, validation policy, signed POST/PUT batch service and per-file complete service/tests. No UI module yet. Establish a non-production private bucket and exact CORS/IAM policy.

## Phase 2 — Redis/Celery media worker foundation

Add Redis config, Celery app/queue routing, `StorageDerivative`, `MediaProcessingJob`, image worker, video poster worker, cleanup/reconcile Beat task, fake-task tests and Docker Compose worker/beat design. No full video transcode.

## Phase 3 — Project Documents core

Add folder tree, file metadata, folder ACL, browse UI, lifecycle and cycle protection.

## Phase 4 — Project Documents upload/preview/share

Add drag/drop queue, batch upload, worker thumbnails/lightbox, authorized search/filter and share modal.

## Phase 5 — Company Media core

Add album model, media file model and album grid, reusing storage/batch contracts.

## Phase 6 — Company Media gallery/ACL

Add drag/drop album upload, gallery/lightbox, album ACL/share, cover and archive/restore.

## Phase 7 — Hardening and deploy

Validate provider CORS/IAM/private bucket/versioning/lifecycle, quota/rate limits, cleanup schedule, audit, worker monitoring, backup/runbook, AV/quarantine decision, production Docker, performance/mobile/accessibility review and security audit.

## Commands to verify after implementation approval

```bash
python -m compileall app tests
pytest -q
flask routes
flask security-audit
flask sync-permissions
flask sync-permissions --apply-defaults
```

Run database migration commands only in their approved deployment runbook, never as an investigation step. Use a disposable test database and test bucket for integration tests; do not point tests at production.

## Rollback notes

Use additive migrations and feature flags/nav gating. On code rollback, leave new tables/object keys untouched; stop issuing URLs for new modules and retain objects for forensic/retention policy. Never blindly delete a bucket prefix as rollback. If completion failures arise, disable presign endpoint, preserve pending metadata, investigate audit/reconciliation, then run an approved targeted cleanup. Existing report local attachments remain independent.
