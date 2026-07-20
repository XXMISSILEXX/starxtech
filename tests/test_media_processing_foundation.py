from io import BytesIO
from PIL import Image
from app.extensions import db
from app.models import StorageObject, StorageDerivative, User
from app.storage.providers import FakeStorageProvider
from app.media_processing.services import enqueue_media_processing_for_storage_object
from app.media_processing.pipeline import process_job

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
