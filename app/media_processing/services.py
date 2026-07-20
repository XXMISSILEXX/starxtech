from datetime import datetime, timedelta
from pathlib import Path
import shutil
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
  for job in jobs:
   if job.storage_object.upload_status=="active":
    job.celery_task_id="reconcile-pending";db.session.commit();enqueue_media_processing_for_storage_object(job.storage_object_id)
   else: job.status="cancelled";db.session.commit()
 return {"matched":len(jobs),"dry_run":dry_run}

def cleanup_media_temp(dry_run=True, older_than_hours=24):
 root=Path(__import__('flask').current_app.config["MEDIA_TEMP_ROOT"]).resolve();root.mkdir(parents=True,exist_ok=True);cutoff=datetime.now().timestamp()-older_than_hours*3600;matched=0
 for child in root.iterdir():
  if child.is_symlink() or not child.is_dir() or child.stat().st_mtime>=cutoff: continue
  matched+=1
  if not dry_run: shutil.rmtree(child,ignore_errors=True)
 return {"matched":matched,"dry_run":dry_run}
