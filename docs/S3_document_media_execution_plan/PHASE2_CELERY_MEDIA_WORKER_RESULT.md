# Phase 2 result

Added Celery integration, Redis configuration, `MediaProcessingJob` and `StorageDerivative` additive models/migration, plus image/video queue task foundation and reconciliation service. PostgreSQL remains the job source of truth; Redis is only delivery/result infrastructure. Hardening adds mockable ffprobe/ffmpeg video poster coverage, duplicate-success no-op behavior, temp-root cleanup that ignores symlinks, and static Celery/media security-audit guards.

Migration: `20260720_0011_add_media_processing_foundation.py`. Dependencies: Celery 5.4.0 and redis 5.0.8. Queues are `media_image`, `media_video`, and `storage_cleanup`.

The worker validates durable job/object state and is idempotent for succeeded/cancelled jobs. It does not modify ReportAttachment or Partner code. Production workers need ffmpeg/ffprobe and a fully configured storage provider; no Docker or production worker was started. Remaining work is operational retry/backoff/Beat scheduling and integration tests against approved private storage, not Phase 3 UI/domain work.

## Worker command (Phase 4.6)

Run Redis locally/system-wide, start Flask normally, then use the Flask-aware entrypoint:

```bash
celery -A app.celery_worker:celery_app worker -Q media_image,media_video,storage_cleanup --loglevel=INFO
```

No `--include` is required: the entrypoint creates the Flask app, configures the Celery `ContextTask`, then imports media tasks. Correct startup lists `media.process_image_derivatives`, `media.process_video_derivatives`, and `media.reconcile_media_jobs`. `Working outside of application context` indicates the old `app.celery_app:celery_app` entrypoint was used; restart with the command above. Existing failed/discarded jobs may be retried by uploading a new image or through an approved future re-enqueue operation.

## Celery result contract

Celery tasks must never return SQLAlchemy model instances: the configured result backend serializes results as JSON. Image/video tasks convert the internal `MediaProcessingJob` result to a JSON-safe summary containing `ok`, `job_id`, `status`, `kind`, and `storage_object_id`; reconciliation returns only primitive summary fields. If the worker reports `MediaProcessingJob is not JSON serializable`, inspect the task return value rather than the internal pipeline result.

Phase 3 should add project document folder/file/ACL models and replace Phase-1 owner-only scope with target ACL checks.
