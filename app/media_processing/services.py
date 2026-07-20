from datetime import datetime
from app.extensions import db
from app.models import MediaProcessingJob, StorageObject

def enqueue_media_processing_for_storage_object(storage_object_id):
 obj=db.session.get(StorageObject,storage_object_id)
 if not obj or obj.upload_status!="active": return None
 kind="image_derivatives" if obj.mime_type.startswith("image/") else "video_derivatives" if obj.mime_type.startswith("video/") else None
 if not kind: obj.processing_status="none";db.session.commit();return None
 job=MediaProcessingJob.query.filter_by(storage_object_id=obj.id,job_type=kind).filter(MediaProcessingJob.status.in_(["pending","processing","succeeded"])).first()
 if job:return job
 job=MediaProcessingJob(storage_object_id=obj.id,job_type=kind,status="pending",max_attempts=3);db.session.add(job);obj.processing_status="queued";db.session.commit()
 from app.media_processing.tasks import process_image_derivatives,process_video_derivatives
 result=(process_image_derivatives if kind=="image_derivatives" else process_video_derivatives).delay(job.id);job.celery_task_id=result.id;db.session.commit();return job

def reconcile_media_jobs(dry_run=True):
 jobs=MediaProcessingJob.query.filter_by(status="pending").filter(MediaProcessingJob.celery_task_id.is_(None)).all()
 if not dry_run:
  for job in jobs: enqueue_media_processing_for_storage_object(job.storage_object_id)
 return {"matched":len(jobs),"dry_run":dry_run}
