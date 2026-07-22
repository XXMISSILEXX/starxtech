from app.celery_app import celery_app


@celery_app.task(name="bulk_download.build_zip")
def build_bulk_zip(job_id):
    from app.bulk_downloads.services import run_job
    return run_job(job_id)


@celery_app.task(name="bulk_download.cleanup_expired")
def cleanup_expired():
    from app.bulk_downloads.services import cleanup_expired_jobs
    return cleanup_expired_jobs()
