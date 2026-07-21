from datetime import datetime
from pathlib import Path
import shutil

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


def enqueue_media_processing_for_storage_object(storage_object_id):
    storage_object = db.session.get(StorageObject, storage_object_id)
    if not storage_object or storage_object.upload_status != "active":
        return None

    job_type = media_job_type_for_storage_object(storage_object)
    if not job_type:
        storage_object.processing_status = "none"
        db.session.commit()
        return None
    if has_ready_derivatives(storage_object):
        storage_object.processing_status = "completed"
        db.session.commit()
        return None

    job = MediaProcessingJob.query.filter_by(
        storage_object_id=storage_object.id,
        job_type=job_type,
    ).filter(MediaProcessingJob.status.in_(["pending", "processing", "succeeded"])).first()
    if job:
        return job

    job = MediaProcessingJob(
        storage_object_id=storage_object.id,
        job_type=job_type,
        status="pending",
        max_attempts=3,
    )
    db.session.add(job)
    storage_object.processing_status = "queued"
    db.session.commit()
    return _dispatch_media_job(job)


def retry_media_jobs(status, dry_run=True):
    if status not in {"pending", "failed"}:
        raise ValueError("Chỉ có thể retry job pending hoặc failed.")

    jobs = MediaProcessingJob.query.filter_by(status=status).order_by(MediaProcessingJob.id).all()
    summary = {
        "status": status,
        "matched": len(jobs),
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
        summary["re_enqueued"] = len(eligible)
        return summary

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


def reconcile_media_jobs(dry_run=True):
    return retry_media_jobs("pending", dry_run=dry_run)


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
