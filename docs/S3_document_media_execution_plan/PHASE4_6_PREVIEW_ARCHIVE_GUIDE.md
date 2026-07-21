# Phase 4.6 — Preview, archive và retry media jobs

## Local services

Run Redis and MinIO/S3-compatible storage configured through environment variables, then start Flask and the Flask-aware worker:

```bash
flask run
celery -A app.celery_worker:celery_app worker -Q media_image,media_video,storage_cleanup --loglevel=INFO
```

The worker task list must include `media.process_image_derivatives`. Do not use the old bare `app.celery_app:celery_app` entrypoint.

## Inspect real model columns

Do not infer ORM attribute names from UI labels. In particular, `MediaProcessingJob` has `job_type` (not `kind`) and `StorageObject` has `file_size` (not `size_bytes`). Inspect the running model definitions with:

```bash
python - <<'PY'
from app import create_app
from app.models import MediaProcessingJob, StorageDerivative, StorageObject, ProjectDocumentFile

app = create_app()
with app.app_context():
    for cls in [MediaProcessingJob, StorageDerivative, StorageObject, ProjectDocumentFile]:
        print(f"\n== {cls.__name__} ==")
        for col in cls.__table__.columns:
            print("-", col.name)
PY
```

Phase 4.6 uses these relevant fields:

- `MediaProcessingJob`: `storage_object_id`, `job_type`, `status`, `celery_task_id`, `attempts`, `error_code`, `error_message`.
- `StorageObject`: `bucket`, `object_key`, `mime_type`, `file_size`, `upload_status`, `processing_status`.
- `StorageDerivative`: `storage_object_id`, `derivative_type`, `bucket`, `object_key`, `mime_type`, `file_size`, `deleted_at`.
- `ProjectDocumentFile`: `folder_id`, `storage_object_id`, `display_name`, `is_active`, `deleted_at`.

## Preview and CSP

The folder page requests a short-lived signed derivative URL only in browser JavaScript. It never renders or stores signed URLs in the database. Images use `thumbnail` for the list and `preview` in the quick-view modal; videos use `poster` only.

With `STORAGE_PROVIDER=s3`, the valid storage endpoint origin is added to CSP `connect-src`, `img-src`, and `media-src`. For MinIO at `http://127.0.0.1:9000`, browser CORS must also allow the actual Flask origin (`http://localhost:5666` differs from `http://127.0.0.1:5666`).

If a derivative exists but no thumbnail appears, verify: worker success, `StorageDerivative.object_key`, `POST /signed-preview`, MinIO CORS, and the CSP `img-src` source.

## Retry old jobs safely

```bash
flask media-jobs status
flask media-jobs retry-pending --dry-run
flask media-jobs retry-pending --apply
flask media-jobs retry-failed --dry-run
flask media-jobs retry-failed --apply
```

`--dry-run` changes nothing. `--apply` only retries active image/video objects whose required derivatives are not already ready; it reuses the existing job, resets its old error metadata, and does not create a duplicate job row. Objects with completed derivatives are skipped.

If jobs remain queued, confirm Redis and the worker are running, then use the appropriate retry command. Archive only soft-deletes `ProjectDocumentFile` metadata; it intentionally does not delete the original object or derivatives from S3/MinIO. If the archive button is missing, verify the user has the file delete permission and folder/project ACL scope.
