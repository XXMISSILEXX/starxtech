from datetime import datetime
from app.celery_app import celery_app
from app.extensions import db
from app.models import MediaProcessingJob

def _run(job_id):
 from app.media_processing.pipeline import process_job
 return process_job(job_id)

@celery_app.task(name="media.process_image_derivatives")
def process_image_derivatives(job_id): return _run(job_id)
@celery_app.task(name="media.process_video_derivatives")
def process_video_derivatives(job_id): return _run(job_id)
@celery_app.task(name="media.reconcile_media_jobs")
def reconcile_media_jobs_task():
 from app.media_processing.services import reconcile_media_jobs
 return reconcile_media_jobs(dry_run=False)
