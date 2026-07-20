# Prompt templates cho các phase

## Prompt Phase 1 — Storage foundation + batch presign

```text
Bạn là senior Flask engineer + S3 storage architect.

Implement Phase 1 theo kế hoạch zip:
- StorageObject
- UploadBatch
- UploadBatchItem
- Provider interface + FakeProvider
- S3Provider config/skeleton
- validation policy
- presign-batch service
- complete-upload service
- signed URL service-level
- tests

Không tạo Project Documents UI.
Không tạo Company Media UI.
Không thay đổi ReportAttachment.
Không thay đổi Partner module.
Không chạy Docker/restart production.

Chạy:
python -m compileall app tests
pytest -q
flask security-audit

Tạo docs/S3_document_media_investigation/PHASE1_STORAGE_FOUNDATION_RESULT.md
Báo migration file, files changed, tests.
```

## Prompt Phase 2 — Celery worker

```text
Bạn là senior Flask/Celery engineer + media processing engineer.

Implement Phase 2:
- Redis/Celery config
- queue routing media_image/media_video/storage_cleanup
- StorageDerivative
- MediaProcessingJob
- image derivative task
- video poster task with ffprobe/ffmpeg
- cleanup/reconcile beat tasks
- fake S3 tests, Celery eager tests
- Docker compose plan update only if approved

Không tạo UI module.
Không full video transcode.
Không đổi ReportAttachment/Partner.

Chạy compileall, pytest, security-audit.
```

## Prompt Phase 3 — Project Documents core

```text
Implement Project Documents core:
- RBAC registry permissions
- folder/file/ACL models
- folder tree services
- browse UI
- breadcrumb
- create/rename/move/archive/restore folder
- ACL helpers
- tests

Không expose bulk upload UI until Phase 4.
```

## Prompt Phase 4 — Project Documents upload/share

```text
Implement Project Documents upload/preview/share:
- drag/drop batch upload queue
- presign-batch integration
- complete-upload creates ProjectDocumentFile
- worker job status UI
- thumbnail grid/lightbox
- signed original/derivative URLs
- share modal
- authorized search/filter
- tests
```

## Prompt Phase 5 — Company Media core

```text
Implement Company Media core:
- album model
- media file model
- permissions
- album grid
- create/edit/archive/restore album
- no child folders
- tests
```

## Prompt Phase 6 — Company Media gallery/ACL

```text
Implement Company Media gallery/ACL:
- album ACL/share
- drag/drop batch upload image/video
- gallery/lightbox
- cover selection
- signed URLs
- media archive/restore
- tests
```
