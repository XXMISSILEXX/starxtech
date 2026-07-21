from app.celery_app import celery_app


def _run(job_id):
    """Run the pipeline and expose only JSON-safe Celery result data."""
    from app.media_processing.pipeline import process_job

    job = process_job(job_id)
    if job is None:
        return {
            "ok": False,
            "job_id": job_id,
            "status": "not_found",
            "kind": None,
            "storage_object_id": None,
        }

    return {
        "ok": job.status == "succeeded",
        "job_id": job.id,
        "status": job.status,
        "kind": job.job_type,
        "storage_object_id": job.storage_object_id,
    }

@celery_app.task(name="media.process_image_derivatives")
def process_image_derivatives(job_id):
    return _run(job_id)


@celery_app.task(name="media.process_video_derivatives")
def process_video_derivatives(job_id):
    return _run(job_id)


@celery_app.task(name="media.reconcile_media_jobs")
def reconcile_media_jobs_task():
    from app.media_processing.services import reconcile_media_jobs

    summary = reconcile_media_jobs(dry_run=False)
    return {
        "matched": int(summary.get("matched", 0)),
        "dry_run": bool(summary.get("dry_run", False)),
    }
