from app.celery_app import celery_app
from celery.exceptions import Ignore


def _run(task, job_id):
    """Run the pipeline and expose only JSON-safe Celery result data."""
    from app.media_processing.pipeline import process_job

    job = process_job(job_id)
    if job is None:
        from app.extensions import db
        db.session.remove()
        retries = task.request.retries
        if retries < 3:
            raise task.retry(countdown=2 ** retries, max_retries=3)
        __import__("logging").getLogger(__name__).error(
            "media task missing durable job after retries job_id=%s", job_id
        )
        raise Ignore()

    return {
        "ok": job.status == "succeeded",
        "job_id": job.id,
        "status": job.status,
        "kind": job.job_type,
        "storage_object_id": job.storage_object_id,
    }

@celery_app.task(bind=True, name="media.process_image_derivatives")
def process_image_derivatives(self, job_id):
    return _run(self, job_id)


@celery_app.task(bind=True, name="media.process_video_derivatives")
def process_video_derivatives(self, job_id):
    return _run(self, job_id)


@celery_app.task(name="media.reconcile_media_jobs")
def reconcile_media_jobs_task():
    from app.media_processing.services import reconcile_media_jobs

    summary = reconcile_media_jobs(dry_run=False)
    return {
        "matched": int(summary.get("matched", 0)),
        "dry_run": bool(summary.get("dry_run", False)),
    }


@celery_app.task(name="reports.cleanup_expired_upload_sessions")
def cleanup_expired_report_upload_sessions_task():
    from app.reports.direct_uploads import cleanup_expired_sessions
    return cleanup_expired_sessions(dry_run=False)
