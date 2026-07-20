# Media processing worker plan

## Architecture

Redis is Celery broker and result backend for operational delivery/status; PostgreSQL `MediaProcessingJob`, `StorageObject` and `StorageDerivative` are the authoritative state. Flask creates/updates DB job rows transactionally after complete-upload, commits, then dispatches by job ID. A periodic reconciler finds DB pending/queued jobs without a valid Celery task and safely re-enqueues them. Redis loss must not lose original or authoritative job state.

Queues: `media_image` for image derivatives, `media_video` for ffprobe/poster, and `storage_cleanup` for pending/object/temp reconciliation. Celery Beat schedules cleanup/reconcile; video concurrency is deliberately lower than image. Result expiry is short because DB preserves history.

## Pipelines

Image task re-loads active StorageObject by internal ID, validates server-generated key and `HEAD`s/downloads original to a per-job temp dir. Pillow opens with decompression-bomb limits, creates bounded thumbnail WebP and preview WebP/JPEG, uploads derivative keys generated server-side, writes derivative rows/job state transactionally, then deletes temp files.

Video task validates active object, fetches to isolated temp dir, runs argument-list `ffprobe` for duration/width/height and `ffmpeg` for a bounded poster frame WebP/JPEG. It does **not** transcode full video in MVP. PDF/document/audio receive MIME icon only and no worker job.

## Retry, timeout and failure

Tasks are idempotent by `(storage_object_id, job_type)`: lock/reload job, no-op if succeeded, reuse/delete incomplete derivative deterministically. Use finite exponential retry (for example three attempts with jitter), explicit soft/hard time limits, image/video size/dimension/duration resource caps, and failure codes without leaking provider credentials. Timeout or terminal failure sets DB `failed`; original remains active; UI shows placeholder and authorized user/admin may retry/cancel under future policy.

No `shell=True`; use `subprocess.run([...], timeout=..., check=...)`, sanitized internal file paths, minimal environment and no client object key. Always cleanup a unique `mkdtemp` directory in `finally`; Beat reconciles leaked temp directories. Worker skips deleted/inactive/failed objects and rechecks object HEAD before processing.

## Docker, operations and monitoring

Future Compose production design has separate `web`, `redis`, `celery-worker-image`, `celery-worker-video`, and `celery-beat` services; workers mount only an ephemeral temp volume and receive S3 credentials by secret, not browser credentials. Set CPU/memory/pids limits, video concurrency 1 or provider-tested value, restart policy, health checks and queue alerts. Logs include job/object IDs, queue, attempt, duration, derivative outcome—not signed URLs, bytes or credentials. Monitor queue depth, oldest job age, success/failure/retry rate, temp disk, derivative latency and cleanup backlog.

Worker failure never removes original. Derivative failure is nonfatal for browsing; placeholders remain. Retry/cancel changes DB job state and is audited. No worker processes a file before it is active or an object key supplied by client.
