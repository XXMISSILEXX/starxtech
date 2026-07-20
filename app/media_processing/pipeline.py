import json, shutil, subprocess, tempfile
from datetime import datetime
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from app.extensions import db
from app.models import MediaProcessingJob, StorageDerivative
from app.storage.keys import generate_original_key
from app.storage.providers import get_storage_provider

def process_job(job_id):
 job=db.session.get(MediaProcessingJob,job_id)
 if not job or job.status in {"succeeded","cancelled"}: return job
 obj=job.storage_object
 if obj.upload_status!="active": job.status="cancelled";db.session.commit();return job
 job.status="processing";job.attempts+=1;job.started_at=datetime.utcnow();obj.processing_status="processing";db.session.commit()
 root=Path(__import__('flask').current_app.config["MEDIA_TEMP_ROOT"]);root.mkdir(parents=True,exist_ok=True);tmp=Path(tempfile.mkdtemp(dir=root));provider=get_storage_provider()
 try:
  provider.head_object(obj.bucket,obj.object_key); source=tmp/"original";provider.download_object(obj.bucket,obj.object_key,source)
  if job.job_type=="image_derivatives": _image(obj,job,source,tmp,provider)
  else: _video(obj,job,source,tmp,provider)
  obj.processing_status="completed";job.status="succeeded";job.finished_at=datetime.utcnow();db.session.commit()
 except Exception as exc:
  job.status="failed";job.finished_at=datetime.utcnow();job.error_code=type(exc).__name__[:100];job.error_message=str(exc)[:300];obj.processing_status="failed";db.session.commit()
 finally: shutil.rmtree(tmp,ignore_errors=True)
 return job

def _save_derivative(obj,job,kind,path,mime,provider):
 key=generate_original_key("webp",__import__('flask').current_app.config["STORAGE_PREFIX"]).replace("originals/","derivatives/").replace(".webp",f"_{kind}.webp")
 existing=StorageDerivative.query.filter_by(storage_object_id=obj.id,derivative_type=kind,deleted_at=None).first()
 if existing:return existing
 provider.upload_object(obj.bucket,key,path,mime); im=Image.open(path)
 row=StorageDerivative(storage_object_id=obj.id,derivative_type=kind,bucket=obj.bucket,object_key=key,mime_type=mime,file_ext="webp",file_size=path.stat().st_size,width=im.width,height=im.height,created_by_job_id=job.id);db.session.add(row);return row

def _image(obj,job,source,tmp,provider):
 Image.MAX_IMAGE_PIXELS=__import__('flask').current_app.config.get("MEDIA_IMAGE_MAX_PIXELS",100_000_000)
 with Image.open(source) as original:
  original.verify()
 with Image.open(source) as original:
  original=original.convert("RGB");obj.width, obj.height=original.size
  for kind,limit in (("thumbnail",__import__('flask').current_app.config["MEDIA_IMAGE_THUMBNAIL_MAX_SIZE"]),("preview",__import__('flask').current_app.config["MEDIA_IMAGE_PREVIEW_MAX_SIZE"])):
   image=original.copy();image.thumbnail((limit,limit));path=tmp/f"{kind}.webp";image.save(path,"WEBP",quality=82,method=4);_save_derivative(obj,job,kind,path,"image/webp",provider)

def _video(obj,job,source,tmp,provider):
 timeout=__import__('flask').current_app.config["CELERY_TASK_TIME_LIMIT_VIDEO_SECONDS"]
 probe=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration:stream=width,height","-of","json",str(source)],capture_output=True,text=True,check=True,timeout=timeout,shell=False)
 data=json.loads(probe.stdout);stream=next((s for s in data.get("streams",[]) if s.get("width")),{});obj.width=stream.get("width");obj.height=stream.get("height");obj.duration_seconds=float(data.get("format",{}).get("duration",0) or 0)
 poster=tmp/"poster.webp";subprocess.run(["ffmpeg","-y","-ss","1","-i",str(source),"-frames:v","1","-vf",f"scale='min({__import__('flask').current_app.config['MEDIA_VIDEO_POSTER_MAX_SIZE']},iw)':-2",str(poster)],capture_output=True,text=True,check=True,timeout=timeout,shell=False);_save_derivative(obj,job,"poster",poster,"image/webp",provider)
