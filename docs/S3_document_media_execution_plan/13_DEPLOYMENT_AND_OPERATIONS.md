# Deployment and Operations Plan

## Docker services

Target production services:

```yaml
web:
  image: construction-relation-management
  command: gunicorn wsgi:app
  depends_on:
    - redis

redis:
  image: redis:7-alpine
  command: redis-server --appendonly yes --maxmemory-policy noeviction
  volumes:
    - redis_data:/data

celery-worker-image:
  image: construction-relation-management
  command: celery -A app.celery_app worker -Q media_image --loglevel=INFO --concurrency=2
  depends_on:
    - redis

celery-worker-video:
  image: construction-relation-management
  command: celery -A app.celery_app worker -Q media_video --loglevel=INFO --concurrency=1
  depends_on:
    - redis

celery-beat:
  image: construction-relation-management
  command: celery -A app.celery_app beat --loglevel=INFO
  depends_on:
    - redis
```

## Required system packages

Worker image needs:

```text
ffmpeg
ffprobe
libjpeg
libwebp
Pillow dependencies
```

Python deps:

```text
celery
redis
boto3
Pillow
```

Pin versions in requirements.

## Environment variables

```text
STORAGE_PROVIDER=s3|fake|disabled
STORAGE_BUCKET
STORAGE_ENDPOINT_URL
STORAGE_REGION
STORAGE_ACCESS_KEY_ID
STORAGE_SECRET_ACCESS_KEY
STORAGE_PREFIX
STORAGE_UPLOAD_URL_TTL_SECONDS
STORAGE_DOWNLOAD_URL_TTL_SECONDS

CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1
CELERY_TASK_ALWAYS_EAGER=false

STORAGE_MAX_FILES_PER_BATCH=20
STORAGE_MAX_BATCH_SIZE_MB=1024
STORAGE_MAX_IMAGE_SIZE_MB=50
STORAGE_MAX_DOCUMENT_SIZE_MB=200
STORAGE_MAX_VIDEO_SIZE_MB=500
STORAGE_MAX_AUDIO_SIZE_MB=200
```

Company Media can now override its own selection, presign, per-file, category,
concurrency, and session-TTL values with the documented `COMPANY_MEDIA_*`
environment variables in `.env.example`. Omit an override to retain the shared
setting fallback; explicit values must be positive integers.

Production secrets should be Docker secrets or equivalent.

## Monitoring

Track:

```text
Redis memory
queue depth per queue
oldest pending job age
job success/failure/retry rate
worker CPU/RAM
video worker duration
temp disk usage
pending upload count
cleanup backlog
signed-url issuance rate
S3 error rate
```

## Production rollout

1. Backup DB.
2. Apply additive migrations.
3. Deploy web with feature flags hidden.
4. Deploy Redis.
5. Deploy workers.
6. Run fake/provider smoke tests.
7. Enable module nav for admin only.
8. Test S3 bucket private/CORS.
9. Enable wider roles gradually.

## Rollback

- Disable module nav.
- Disable presign endpoints by config.
- Stop workers if needed.
- Keep DB rows/S3 objects.
- Do not delete bucket prefixes without approved cleanup.
