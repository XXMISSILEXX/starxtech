# Test Strategy

## Baseline requirement

Before new phases:

```bash
python -m compileall app tests
pytest -q
flask security-audit
```

Existing modules must remain green.

## Phase 1 tests: Storage + batch

### StorageObject

- create pending.
- unique bucket/object_key.
- valid statuses only.
- object_key does not include original filename.
- client object_key ignored/rejected.

### Validation

- accept valid image/document/video/audio.
- reject exe/html/svg/js/sh/bat/php/jar.
- reject size 0.
- reject size over cap.
- reject MIME/ext mismatch.
- reject invalid checksum format.

### Batch presign

- mixed file types accepted.
- invalid item rejected per item.
- accepted item creates UploadBatchItem + StorageObject.
- rejected item has no StorageObject.
- duplicate client_file_id rejected.
- too many files rejected.
- total batch size rejected.
- partial success works.
- signed response has expiry.
- no signed URL persisted.

### Complete upload

- HEAD missing fails.
- HEAD size mismatch fails.
- success pending -> active.
- idempotent repeat complete.
- ACL revoked after presign blocks complete.
- no worker job if complete fails.
- batch counters update.

## Phase 2 tests: Celery/worker

Use fake S3 and Celery eager/fake transport for unit tests.

- image derivative success.
- video poster with mocked ffprobe/ffmpeg.
- inactive/deleted object skipped.
- duplicate task no-op.
- timeout marks failed.
- max retry terminal failed.
- temp directory cleanup success/fail.
- generated derivative key server-only.
- unique active derivative per object/type.
- Redis loss simulated by missing Celery task, reconciler re-enqueues DB pending job.

## Phase 3/4 tests: Project Documents

- module access per role.
- project assignment prerequisite.
- folder create/rename/move.
- sibling duplicate rejected.
- self/descendant move rejected.
- folder ACL user/role.
- restricted/inherited policy as approved.
- upload only with folder upload ACL.
- search does not reveal unauthorized files.
- signed URL requires view/download.
- archived folder hides descendants from active browse.
- share/revoke audit.
- drag/drop queue UI smoke test if frontend tests available.

## Phase 5/6 tests: Company Media

- album only one level.
- album ACL view/upload/manage/delete/share.
- no child folder route.
- upload only images/videos.
- album grid only authorized.
- cover must belong to album.
- gallery signed URLs lazy.
- archive/restore.

## Security regression

- CSRF for all POST.
- No GET mutation.
- no signed URL in DB/audit.
- report attachment tests unchanged.
- Partner module tests unchanged.
- canonical RBAC tests unchanged.
- security audit no FAIL.
