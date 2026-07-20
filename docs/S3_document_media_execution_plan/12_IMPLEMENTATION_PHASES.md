# Implementation Phases

## Pre-phase baseline

Before every phase:

```bash
python -m compileall app tests
pytest -q
flask security-audit
```

No phase starts if baseline is red.

---

## Phase 1 — Storage foundation + batch presign contract

### Goal

Build independent storage foundation for future modules.

### Scope

- Config env/secrets.
- Storage provider interface.
- Fake provider.
- S3 provider or skeleton.
- StorageObject.
- UploadBatch.
- UploadBatchItem.
- Validation policy.
- Batch presign service.
- Per-file complete service.
- Signed download service at service level.
- Tests.

### Out of scope

- No UI module.
- No Celery worker.
- No Project Documents UI.
- No Company Media UI.
- No ReportAttachment changes.

### Output

- Additive migration.
- `docs/.../PHASE1_STORAGE_FOUNDATION_RESULT.md`
- Tests pass.

---

## Phase 2 — Redis/Celery media worker foundation

### Goal

Process images/videos asynchronously.

### Scope

- Redis config.
- Celery app.
- Queue routing.
- Celery Beat.
- StorageDerivative.
- MediaProcessingJob.
- Image worker.
- Video poster worker.
- Cleanup/reconcile tasks.
- Docker Compose worker/beat plan.
- Tests.

### Output

- Additive migration.
- Worker can process with fake S3/test fixtures.
- No UI module yet.

---

## Phase 3 — Project Documents core

### Goal

Create document folder/file module shell.

### Scope

- Permission registry.
- Module card/sidebar gated.
- Folder tree model.
- ProjectDocumentFile metadata.
- Folder ACL model/helpers.
- Browse UI.
- Breadcrumb.
- Folder create/rename/move/archive/restore.
- No full upload UI yet or only minimal stub.

---

## Phase 4 — Project Documents upload/preview/share

### Goal

Full document upload/view UX.

### Scope

- Drag/drop queue.
- Presign batch integration.
- Complete upload creates domain files.
- Worker processing status.
- Thumbnail grid.
- Lightbox/gallery.
- Signed URL original/derivative.
- Share modal.
- Search/filter.
- Audit.

---

## Phase 5 — Company Media core

### Goal

Create album/media module shell.

### Scope

- Permissions.
- Album model.
- Media file model.
- Album grid.
- Album create/edit/archive/restore.
- No subfolders.

---

## Phase 6 — Company Media gallery/ACL

### Goal

Full album upload/gallery.

### Scope

- Album ACL/share.
- Drag/drop upload images/videos.
- Gallery/lightbox.
- Cover selection.
- Search/filter.
- Archive/restore media.
- Audit.

---

## Phase 7 — Hardening/deploy

### Scope

- S3 CORS/IAM/private bucket validation.
- Quotas.
- Rate limits.
- Cleanup schedules.
- Monitoring/alerts.
- Worker resource limits.
- AV/quarantine decision.
- Backup/restore runbook.
- Production Docker.
- Security audit.

## Rollback rules

- Additive migrations only.
- Code rollback leaves tables/objects intact.
- Disable presign endpoints if storage issue.
- Never delete bucket prefix blindly.
- Existing reports remain independent.
