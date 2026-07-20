# Redis + Celery Media Worker Plan

## Architecture

```text
Flask complete-upload
  -> DB transaction: StorageObject active + MediaProcessingJob pending
  -> commit
  -> enqueue Celery task(job_id)
  -> Redis broker

Celery worker
  -> load job from PostgreSQL
  -> load StorageObject
  -> process original from S3
  -> upload derivatives to S3
  -> write StorageDerivative
  -> mark job succeeded/failed
```

PostgreSQL is authoritative. Redis loss does not lose original or job metadata.

## Queues

Recommended queues:

```text
media_image
media_video
storage_cleanup
```

Worker deployment:

```text
celery-worker-image:
  queue: media_image
  concurrency: 1-2

celery-worker-video:
  queue: media_video
  concurrency: 1

celery-beat:
  scheduled cleanup/reconcile
```

## Image pipeline

Task: `process_image_derivatives(job_id)`

Steps:

1. Load `MediaProcessingJob`.
2. No-op if already succeeded.
3. Lock/reload job.
4. Ensure StorageObject active and image MIME.
5. HEAD object.
6. Download original to per-job temp dir.
7. Pillow open with decompression bomb limits.
8. Read width/height.
9. Create thumbnail:
   - WebP.
   - long edge 480 px.
10. Create preview:
   - WebP/JPEG.
   - long edge 1600 px.
11. Upload derivatives with server-generated object keys.
12. Write `StorageDerivative` records.
13. Update `StorageObject.width/height/processing_status`.
14. Mark job succeeded.
15. Cleanup temp dir in `finally`.

## Video pipeline

Task: `process_video_derivatives(job_id)`

Steps:

1. Load job and object.
2. Ensure object active and video MIME.
3. Download original to temp dir.
4. Run `ffprobe` with argument list.
5. Extract duration/width/height.
6. Choose poster timestamp:
   - 1 second if duration > 2s.
   - otherwise 10% duration or first frame.
7. Run `ffmpeg` with argument list, timeout.
8. Create poster WebP/JPEG long edge 720 px.
9. Upload poster derivative.
10. Update `StorageObject.duration_seconds/width/height`.
11. Mark job succeeded.

No full video transcoding in MVP.

## Celery config

Recommended:

```text
task_acks_late = True
worker_prefetch_multiplier = 1
task_track_started = True
task_time_limit:
  image = 120s
  video = 600s
task_soft_time_limit:
  image = 90s
  video = 540s
result_expires = 3600
max_retries = 3
retry_backoff = True
retry_jitter = True
```

## Idempotency

Key rule:

```text
(storage_object_id, job_type) must be idempotent.
```

If duplicate task arrives:

- If job succeeded: no-op.
- If processing stale: reset/retry by reconciler.
- If derivative exists for same type: reuse/replace deterministically with transaction.
- Never create duplicate active derivative for same type.

## Cleanup and reconciliation

Celery Beat tasks:

```text
storage.cleanup_pending_uploads
media.requeue_stuck_jobs
media.cleanup_temp_dirs
storage.reconcile_objects
```

Recommended schedules:

```text
cleanup pending uploads: hourly
requeue stuck jobs: every 10 minutes
temp cleanup: hourly
reconciliation report: daily
```
