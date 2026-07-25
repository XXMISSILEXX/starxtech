from datetime import datetime
from pathlib import Path
import shutil
from flask import current_app

from app.extensions import db
from app.models import MediaProcessingJob, StorageDerivative, StorageObject


def media_job_type_for_storage_object(storage_object):
    if storage_object.mime_type.startswith("image/"):
        return "image_derivatives"
    if storage_object.mime_type.startswith("video/"):
        return "video_derivatives"
    return None


def expected_derivative_types(storage_object):
    job_type = media_job_type_for_storage_object(storage_object)
    if job_type == "image_derivatives":
        return {"thumbnail", "preview"}
    if job_type == "video_derivatives":
        return {"poster"}
    return set()


def has_ready_derivatives(storage_object):
    expected = expected_derivative_types(storage_object)
    if not expected:
        return False
    found = {
        derivative.derivative_type
        for derivative in StorageDerivative.query.filter(
            StorageDerivative.storage_object_id == storage_object.id,
            StorageDerivative.deleted_at.is_(None),
            StorageDerivative.object_key.is_not(None),
            StorageDerivative.object_key != "",
        ).all()
    }
    return expected.issubset(found)


def _dispatch_media_job(job):
    from app.media_processing.tasks import process_image_derivatives, process_video_derivatives

    task = process_image_derivatives if job.job_type == "image_derivatives" else process_video_derivatives
    result = task.delay(job.id)
    job.celery_task_id = result.id
    db.session.commit()
    return job


def stage_media_processing_jobs(storage_objects):
    """Create durable pending jobs in the caller's open transaction.

    This function intentionally does not commit or touch Celery.  Daily Report
    finalization uses it so attachment ownership and job rows become durable
    atomically before any external task is sent.
    """
    job_ids = []
    for storage_object in storage_objects:
        if not storage_object or storage_object.upload_status != "active":
            continue
        job_type = media_job_type_for_storage_object(storage_object)
        if not job_type:
            storage_object.processing_status = "none"
            continue
        if has_ready_derivatives(storage_object):
            storage_object.processing_status = "completed"
            continue
        job = MediaProcessingJob.query.filter_by(
            storage_object_id=storage_object.id, job_type=job_type,
        ).filter(MediaProcessingJob.status.in_(["pending", "processing", "succeeded"])).first()
        if job is None:
            job = MediaProcessingJob(
                storage_object_id=storage_object.id, job_type=job_type,
                status="pending", max_attempts=3,
            )
            db.session.add(job)
            db.session.flush()
        storage_object.processing_status = "queued"
        job_ids.append(job.id)
    return job_ids


def dispatch_media_processing_job(job_id):
    """Dispatch a job only after its owning transaction has committed."""
    job = db.session.get(MediaProcessingJob, job_id)
    if not job or job.status != "pending":
        return job
    if current_app.testing:
        return job
    return _dispatch_media_job(job)


def enqueue_media_processing_for_storage_object(storage_object_id):
    storage_object = db.session.get(StorageObject, storage_object_id)
    if not storage_object or storage_object.upload_status != "active":
        return None

    job_ids = stage_media_processing_jobs([storage_object])
    db.session.commit()
    if not job_ids:
        return None
    job = db.session.get(MediaProcessingJob, job_ids[0])
    # Upload must remain durable even when the optional async worker/broker is
    # temporarily unavailable. Reconciliation/retry commands will dispatch it.
    try:
        return dispatch_media_processing_job(job.id)
    except Exception:
        return job


def retry_media_jobs(status, dry_run=True, module=None):
    if status not in {"pending", "failed"}:
        raise ValueError("Chỉ có thể retry job pending hoặc failed.")

    query = MediaProcessingJob.query.join(StorageObject).filter(MediaProcessingJob.status == status)
    if module:
        query = query.filter(StorageObject.storage_module == module)
    jobs = query.order_by(MediaProcessingJob.id).all()
    summary = {
        "status": status,
        "matched": len(jobs),
        "eligible": 0,
        "dispatched": 0,
        "re_enqueued": 0,
        "skipped": 0,
        "failed_to_enqueue": 0,
        "dry_run": dry_run,
    }
    eligible = []
    for job in jobs:
        storage_object = job.storage_object
        if (
            storage_object is None
            or storage_object.upload_status != "active"
            or media_job_type_for_storage_object(storage_object) != job.job_type
            or has_ready_derivatives(storage_object)
        ):
            summary["skipped"] += 1
            continue
        eligible.append(job)

    if dry_run:
        summary["eligible"] = len(eligible)
        summary["re_enqueued"] = len(eligible)
        return summary

    summary["eligible"] = len(eligible)

    for job in eligible:
        storage_object = job.storage_object
        job.status = "pending"
        job.celery_task_id = None
        job.attempts = 0
        job.started_at = None
        job.finished_at = None
        job.error_code = None
        job.error_message = None
        storage_object.processing_status = "queued"
    db.session.commit()

    for job in eligible:
        try:
            _dispatch_media_job(job)
        except Exception:
            db.session.rollback()
            summary["failed_to_enqueue"] += 1
        else:
            summary["re_enqueued"] += 1
            summary["dispatched"] += 1
    return summary


def media_jobs_status():
    counts = {
        status: MediaProcessingJob.query.filter_by(status=status).count()
        for status in ("pending", "processing", "succeeded", "failed", "cancelled")
    }
    return {
        "jobs": counts,
        "ready_storage_objects": sum(
            1 for storage_object in StorageObject.query.filter(
                StorageObject.upload_status == "active"
            ).all() if has_ready_derivatives(storage_object)
        ),
    }


def reconcile_media_jobs(dry_run=True, module=None):
    return retry_media_jobs("pending", dry_run=dry_run, module=module)


def cleanup_media_temp(dry_run=True, older_than_hours=24):
    root = Path(__import__("flask").current_app.config["MEDIA_TEMP_ROOT"]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    cutoff = datetime.now().timestamp() - older_than_hours * 3600
    matched = 0
    for child in root.iterdir():
        if child.is_symlink() or not child.is_dir() or child.stat().st_mtime >= cutoff:
            continue
        matched += 1
        if not dry_run:
            shutil.rmtree(child, ignore_errors=True)
    return {"matched": matched, "dry_run": dry_run}
