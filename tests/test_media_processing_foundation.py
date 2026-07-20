from io import BytesIO
import subprocess
from unittest.mock import patch
from pathlib import Path
from PIL import Image
from app.extensions import db
from app.models import StorageObject, StorageDerivative, User
from app.storage.providers import FakeStorageProvider
from app.media_processing.services import enqueue_media_processing_for_storage_object
from app.media_processing.pipeline import process_job
from app.models import MediaProcessingJob
from app.media_processing.services import cleanup_media_temp, reconcile_media_jobs

def test_image_pipeline_creates_derivatives(app, tmp_path):
 with app.app_context():
  provider=FakeStorageProvider();app.extensions["storage_provider"]=provider;app.config["MEDIA_TEMP_ROOT"]=str(tmp_path)
  buf=BytesIO();Image.new("RGB",(1000,600),"red").save(buf,"JPEG")
  obj=StorageObject(bucket="b",object_key="originals/a.jpg",original_filename="a.jpg",mime_type="image/jpeg",file_ext="jpg",file_size=len(buf.getvalue()),uploaded_by_id=3,upload_status="active")
  db.session.add(obj);db.session.commit();provider.put_bytes("b",obj.object_key,buf.getvalue(),"image/jpeg")
  job=enqueue_media_processing_for_storage_object(obj.id);process_job(job.id)
  assert job.status=="succeeded" and obj.processing_status=="completed" and StorageDerivative.query.count()==2 and obj.width==1000

def test_non_media_does_not_enqueue(app):
 with app.app_context():
  obj=StorageObject(bucket="b",object_key="originals/a.pdf",original_filename="a.pdf",mime_type="application/pdf",file_ext="pdf",file_size=1,uploaded_by_id=3,upload_status="active");db.session.add(obj);db.session.commit()
  assert enqueue_media_processing_for_storage_object(obj.id) is None

def test_video_pipeline_uses_safe_argument_lists(app, tmp_path):
 with app.app_context():
  provider=FakeStorageProvider();app.extensions["storage_provider"]=provider;app.config["MEDIA_TEMP_ROOT"]=str(tmp_path)
  obj=StorageObject(bucket="b",object_key="originals/a.mp4",original_filename="a.mp4",mime_type="video/mp4",file_ext="mp4",file_size=3,uploaded_by_id=3,upload_status="active");db.session.add(obj);db.session.commit();provider.put_bytes("b",obj.object_key,b"vid","video/mp4")
  job=enqueue_media_processing_for_storage_object(obj.id)
  def fake_run(args, **kwargs):
   assert isinstance(args,list) and kwargs.get("shell") is False
   if args[0]=="ffprobe": return subprocess.CompletedProcess(args,0,'{"format":{"duration":"4"},"streams":[{"width":640,"height":360}]}','')
   Path(args[-1]).write_bytes(BytesIO().getvalue() or b"RIFF")
   from PIL import Image; Image.new("RGB",(20,20)).save(args[-1],"WEBP")
   return subprocess.CompletedProcess(args,0,'','')
  with patch("app.media_processing.pipeline.subprocess.run",side_effect=fake_run): process_job(job.id)
  assert job.status=="succeeded" and StorageDerivative.query.filter_by(derivative_type="poster").count()==1

def test_video_failure_and_temp_cleanup(app,tmp_path):
 with app.app_context():
  app.config["MEDIA_TEMP_ROOT"]=str(tmp_path);outside=tmp_path.parent/"outside";outside.mkdir(exist_ok=True);link=tmp_path/"link";link.symlink_to(outside,target_is_directory=True)
  old=tmp_path/"old";old.mkdir();old.touch()
  assert cleanup_media_temp(dry_run=False,older_than_hours=0)["matched"]>=1
  assert outside.exists() and link.exists()
