from app.extensions import db
from app.models import AuditLog, CompanyMediaAlbum, CompanyMediaFile, StorageObject, User
from app.storage.providers import FakeStorageProvider


def _login(client, username):
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def _album_with_files(app, count=1):
    with app.app_context():
        admin = db.session.get(User, 6)
        album = CompanyMediaAlbum(name="Album audit media", created_by_id=admin.id)
        db.session.add(album)
        db.session.flush()
        files = []
        for index in range(count):
            storage = StorageObject(
                bucket="test",
                object_key=f"company-media/audit-{album.id}-{index}.jpg",
                original_filename=f"original-{index}.jpg",
                mime_type="image/jpeg",
                file_ext="jpg",
                file_size=index + 5,
                uploaded_by_id=admin.id,
                upload_status="active",
                processing_status="none",
            )
            db.session.add(storage)
            db.session.flush()
            file = CompanyMediaFile(
                album_id=album.id,
                storage_object_id=storage.id,
                display_name=f"display-{index}.jpg",
                media_type="image",
                created_by_id=admin.id,
            )
            db.session.add(file)
            files.append(file)
        db.session.commit()
        return album.id, [file.id for file in files]


def test_individual_media_archive_records_complete_snapshot(client, app):
    album_id, (file_id,) = _album_with_files(app)
    _login(client, "admin")

    response = client.post(f"/company-media/files/{file_id}/archive")

    assert response.status_code == 302
    with app.app_context():
        record = AuditLog.query.filter_by(action="company_media.file.delete").one()
        assert record.entity_type == "CompanyMediaFile"
        assert record.entity_id == file_id
        snapshot = record.old_values_json
        assert set(snapshot) == {
            "file_name", "original_filename", "created_by_id", "created_at", "file_size",
            "storage_object_id", "object_key", "album_id",
        }
        assert snapshot["file_name"] == "display-0.jpg"
        assert snapshot["original_filename"] == "original-0.jpg"
        assert snapshot["created_by_id"] == 6
        assert snapshot["created_at"]
        assert snapshot["file_size"] == 5
        assert snapshot["storage_object_id"]
        assert snapshot["object_key"] == f"company-media/audit-{album_id}-0.jpg"
        assert snapshot["album_id"] == album_id
        media = db.session.get(CompanyMediaFile, file_id)
        assert media.is_active is False
        assert media.updated_by_id == 6


def test_bulk_media_archive_records_once_and_sets_each_updater(client, app):
    album_id, file_ids = _album_with_files(app, count=3)
    _login(client, "admin")

    response = client.post(f"/company-media/albums/{album_id}/files/bulk-archive", json={"file_ids": file_ids})

    assert response.status_code == 200
    assert response.get_json()["archived"] == 3
    with app.app_context():
        records = AuditLog.query.filter_by(action="company_media.file.delete").all()
        assert len(records) == 1
        snapshot = records[0].old_values_json
        assert snapshot["album_id"] == album_id
        assert snapshot["file_count"] == 3
        assert len(snapshot["files"]) == 3
        assert {item["file_name"] for item in snapshot["files"]} == {
            "display-0.jpg", "display-1.jpg", "display-2.jpg",
        }
        assert {db.session.get(CompanyMediaFile, file_id).updated_by_id for file_id in file_ids} == {6}


def test_media_restore_records_for_individual_and_bulk(client, app):
    album_id, file_ids = _album_with_files(app, count=3)
    _login(client, "admin")
    assert client.post(f"/company-media/files/{file_ids[0]}/archive").status_code == 302
    assert client.post(f"/company-media/files/{file_ids[0]}/restore").status_code == 302
    assert client.post(f"/company-media/albums/{album_id}/files/bulk-archive", json={"file_ids": file_ids[1:]}).status_code == 200
    assert client.post(f"/company-media/albums/{album_id}/files/bulk-restore", json={"file_ids": file_ids[1:]}).status_code == 200

    with app.app_context():
        restores = AuditLog.query.filter_by(action="company_media.file.restore").order_by(AuditLog.id).all()
        assert len(restores) == 2
        assert restores[0].entity_id == file_ids[0]
        assert restores[1].old_values_json["file_count"] == 2
        assert all(db.session.get(CompanyMediaFile, file_id).updated_by_id == 6 for file_id in file_ids)


def test_bulk_media_download_records_once(client, app, tmp_path):
    album_id, file_ids = _album_with_files(app, count=3)
    with app.app_context():
        provider = FakeStorageProvider()
        app.extensions["storage_provider"] = provider
        app.config["BULK_DOWNLOAD_TEMP_ROOT"] = str(tmp_path)
        for file_id in file_ids:
            media = db.session.get(CompanyMediaFile, file_id)
            provider.put_bytes(media.storage_object.bucket, media.storage_object.object_key, b"image", "image/jpeg")
    _login(client, "admin")

    response = client.post(f"/company-media/albums/{album_id}/files/bulk-signed-download", json={"file_ids": file_ids})

    assert response.status_code == 200
    response.get_data()
    response.close()
    with app.app_context():
        records = AuditLog.query.filter_by(action="bulk_download.create").all()
        assert len(records) == 1
        snapshot = records[0].new_values_json
        assert snapshot["album_id"] == album_id
        assert snapshot["file_count"] == 3
        assert snapshot["total_size_bytes"] == 18
        assert len(snapshot["files"]) == 3


def test_denied_media_archive_changes_nothing_and_records_nothing(client, app):
    _album_id, (file_id,) = _album_with_files(app)
    with app.app_context():
        before = AuditLog.query.count()
    _login(client, "viewer")

    response = client.post(f"/company-media/files/{file_id}/archive")

    assert response.status_code == 403
    with app.app_context():
        media = db.session.get(CompanyMediaFile, file_id)
        assert media.is_active is True
        assert media.deleted_at is None
        assert media.updated_by_id is None
        assert AuditLog.query.count() == before


def test_media_preview_and_thumbnail_do_not_record_audit(client, app):
    _album_id, (file_id,) = _album_with_files(app)
    with app.app_context():
        before = AuditLog.query.count()
    _login(client, "admin")

    preview = client.post(f"/company-media/files/{file_id}/signed-preview", json={})
    thumbnail = client.get(f"/company-media/files/{file_id}/thumbnail")

    assert preview.status_code == 200
    assert thumbnail.status_code == 200
    thumbnail.close()
    with app.app_context():
        assert AuditLog.query.count() == before
