from datetime import datetime, timedelta

from app.extensions import db
from app.admin_storage.services import normalize_module_label, normalize_source_type_label
from app.models import BulkDownloadJob, DownloadEvent, StorageDerivative, StorageObject, User


def _login(client, username):
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def _object(user_id=1, size=100, module="company_media"):
    item = StorageObject(bucket="test", object_key=f"test/{datetime.now().timestamp()}", original_filename="large.jpg", mime_type="image/jpeg", file_ext="jpg", file_size=size, uploaded_by_id=user_id, upload_status="active", storage_module=module)
    db.session.add(item); db.session.flush()
    return item


def test_dashboard_permissions_and_csv(client):
    assert client.get("/admin/storage").status_code == 302
    _login(client, "viewer")
    assert client.get("/admin/storage").status_code == 200
    assert client.get("/admin/storage/export.csv").status_code == 403
    client.post("/logout")
    _login(client, "admin")
    assert client.get("/admin/storage").status_code == 200
    assert client.get("/admin/storage/export.csv").status_code == 403
    client.post("/logout")
    _login(client, "super")
    response = client.get("/admin/storage/export.csv")
    assert response.status_code == 200
    assert response.content_type.startswith("text/csv")
    assert response.data.startswith(b"\xef\xbb\xbfsection")


def test_dashboard_aggregates_metadata_and_events(app, client):
    with app.app_context():
        item = _object(size=100)
        unknown = _object(size=10, module=None)
        empty_module = _object(size=5, module="")
        document_library = _object(size=15, module="document-library")
        db.session.add(StorageDerivative(storage_object_id=item.id, derivative_type="thumbnail", bucket="test", object_key="test/thumbnail", mime_type="image/jpeg", file_ext="jpg", file_size=20))
        db.session.add(BulkDownloadJob(module="company-media", status="succeeded", requested_by_id=1, source_context_type="album", source_context_id=1, requested_file_ids=[], file_count=0, total_size_bytes=0, zip_filename="bundle.zip", zip_size_bytes=30, expires_at=datetime.utcnow() + timedelta(days=1)))
        db.session.add(DownloadEvent(user_id=1, storage_object_id=item.id, kind="download", module="company_media", source_type="single", estimated_bytes=40, estimated_storage_egress_bytes=50, estimated_client_egress_bytes=60))
        db.session.add(DownloadEvent(user_id=1, storage_object_id=unknown.id, kind="download", module=None, source_type=None, estimated_bytes=10))
        db.session.commit()
    _login(client, "super")
    page = client.get("/admin/storage")
    assert page.status_code == 200
    assert b"180,0 B" in page.data
    assert "Không xác định / legacy".encode() in page.data
    assert "Hồ sơ tài liệu".encode() in page.data
    assert b"Dung l" in page.data
    csv = client.get("/admin/storage/export.csv")
    assert b"legacy_zip,30" in csv.data
    assert b"top_object,large.jpg,60" in csv.data


def test_storage_dashboard_label_normalizers():
    assert normalize_module_label(None) == "Không xác định / legacy"
    assert normalize_module_label("") == "Không xác định / legacy"
    assert normalize_module_label("document-library") == "Hồ sơ tài liệu"
    assert normalize_module_label("company-media") == "Thư viện ảnh/video công ty"
    assert normalize_source_type_label(None) == "Không xác định / legacy"
    assert normalize_source_type_label("original") == "Tải file gốc"
    assert normalize_source_type_label("zip_stream") == "Tải ZIP"
