"""Phase 13 destructive audit snapshots; SQLite does not prove PostgreSQL concurrency behavior."""

from app.extensions import db
from app.models import (AuditLog, Company, CompanyMediaAlbum, CompanyMediaFile, Customer, Partner,
    Project, ProjectDocumentFile, ProjectDocumentFolder, StorageObject, User)
from app.project_documents.services import create_folder, get_or_create_project_root_folder


def _login(client, username):
    client.post("/login", data={"username_or_email": username, "password": "password123"})


def _document_folder_with_children(app):
    with app.app_context():
        admin = db.session.get(User, 6)
        project = db.session.get(Project, 1)
        root = get_or_create_project_root_folder(project, admin)
        folder = create_folder(admin, root, "Hồ sơ nghiệm thu")
        child_folder = create_folder(admin, folder, "Bản vẽ con")
        objects = [
            StorageObject(
                bucket="test",
                object_key=f"project-documents/audit-snapshot-{index}.pdf",
                original_filename=f"goc-{index}.pdf",
                mime_type="application/pdf",
                file_ext="pdf",
                file_size=index + 10,
                uploaded_by_id=admin.id,
                upload_status="active",
            )
            for index in range(2)
        ]
        db.session.add_all(objects)
        db.session.flush()
        files = [
            ProjectDocumentFile(
                project_id=project.id,
                folder_id=folder.id,
                storage_object_id=storage.id,
                display_name=f"Tệp {index + 1}.pdf",
                created_by_id=admin.id,
            )
            for index, storage in enumerate(objects)
        ]
        db.session.add_all(files)
        db.session.commit()
        return {
            "root_id": root.id,
            "folder_id": folder.id,
            "child_folder_id": child_folder.id,
            "file_ids": [document_file.id for document_file in files],
            "object_keys": [storage.object_key for storage in objects],
        }


def _album_with_files(app):
    with app.app_context():
        admin = db.session.get(User, 6)
        album = CompanyMediaAlbum(name="Album snapshot Phase 13", created_by_id=admin.id)
        db.session.add(album)
        db.session.flush()
        objects = [
            StorageObject(
                bucket="test",
                object_key=f"company-media/album-snapshot-{index}.jpg",
                original_filename=f"goc-media-{index}.jpg",
                mime_type="image/jpeg",
                file_ext="jpg",
                file_size=index + 20,
                uploaded_by_id=admin.id,
                upload_status="active",
                processing_status="none",
            )
            for index in range(2)
        ]
        db.session.add_all(objects)
        db.session.flush()
        files = [
            CompanyMediaFile(
                album_id=album.id,
                storage_object_id=storage.id,
                display_name=f"Media {index + 1}.jpg",
                media_type="image",
                created_by_id=admin.id,
            )
            for index, storage in enumerate(objects)
        ]
        db.session.add_all(files)
        db.session.commit()
        return album.id, [media.id for media in files], [storage.object_key for storage in objects]


def test_document_file_archive_and_restore_snapshot_include_file_parent_and_project(client, app):
    data = _document_folder_with_children(app)
    file_id = data["file_ids"][0]
    _login(client, "admin")

    assert client.post(f"/project-documents/files/{file_id}/archive").status_code == 302
    with app.app_context():
        archived = AuditLog.query.filter_by(action="document.file.archive", entity_id=file_id).one()
        snapshot = archived.old_values_json
        assert snapshot["file_name"] == "Tệp 1.pdf"
        assert snapshot["original_filename"] == "goc-0.pdf"
        assert snapshot["created_by_id"] == 6
        assert snapshot["created_at"]
        assert snapshot["file_size"] == 10
        assert snapshot["object_key"] == data["object_keys"][0]
        assert snapshot["folder"] == {"id": data["folder_id"], "name": "Hồ sơ nghiệm thu"}
        assert snapshot["project"]["id"] == 1

    assert client.post(f"/project-documents/files/{file_id}/restore").status_code == 302
    with app.app_context():
        restored = AuditLog.query.filter_by(action="document.file.restore", entity_id=file_id).one()
        assert restored.old_values_json["object_key"] == data["object_keys"][0]
        assert restored.old_values_json["folder"]["id"] == data["folder_id"]
        assert restored.old_values_json["project"]["id"] == 1


def test_bulk_document_file_archive_and_restore_snapshots_include_object_key(client, app):
    data = _document_folder_with_children(app)
    file_id = data["file_ids"][1]
    _login(client, "admin")

    archived = client.post(
        f"/project-documents/folders/{data['folder_id']}/files/bulk-archive",
        json={"file_ids": [file_id]},
    )
    assert archived.status_code == 200
    with app.app_context():
        record = AuditLog.query.filter_by(action="document.file.archive", entity_id=file_id).one()
        assert record.old_values_json["object_key"] == data["object_keys"][1]

    restored = client.post(
        f"/project-documents/folders/{data['folder_id']}/files/bulk-restore",
        json={"file_ids": [file_id]},
    )
    assert restored.status_code == 200
    with app.app_context():
        record = AuditLog.query.filter_by(action="document.file.restore", entity_id=file_id).one()
        assert record.old_values_json["object_key"] == data["object_keys"][1]


def test_document_folder_archive_and_restore_snapshot_summarize_hidden_children(client, app):
    data = _document_folder_with_children(app)
    _login(client, "admin")

    assert client.post(f"/project-documents/folders/{data['folder_id']}/archive").status_code == 302
    with app.app_context():
        archived = AuditLog.query.filter_by(action="document.folder.archive", entity_id=data["folder_id"]).one()
        snapshot = archived.old_values_json
        assert snapshot["folder_name"] == "Hồ sơ nghiệm thu"
        assert snapshot["project"]["id"] == 1
        assert snapshot["parent_path"][-1]["id"] == data["root_id"]
        assert snapshot["child_count"] == 3
        assert snapshot["file_count"] == 2
        assert snapshot["folder_count"] == 1
        assert snapshot["truncated_child_count"] == 0
        assert {child["name"] for child in snapshot["children"]} == {"Tệp 1.pdf", "Tệp 2.pdf", "Bản vẽ con"}

    assert client.post(f"/project-documents/folders/{data['folder_id']}/restore").status_code == 302
    with app.app_context():
        restored = AuditLog.query.filter_by(action="document.folder.restore", entity_id=data["folder_id"]).one()
        assert restored.old_values_json["child_count"] == 3
        assert {child["name"] for child in restored.old_values_json["children"]} == {
            "Tệp 1.pdf", "Tệp 2.pdf", "Bản vẽ con",
        }


def test_company_media_album_archive_and_restore_snapshot_summarize_files(client, app):
    album_id, _file_ids, object_keys = _album_with_files(app)
    _login(client, "admin")

    assert client.post(f"/company-media/albums/{album_id}/archive").status_code == 302
    with app.app_context():
        archived = AuditLog.query.filter_by(action="company_media.album.archive", entity_id=album_id).one()
        snapshot = archived.old_values_json
        assert snapshot["album_name"] == "Album snapshot Phase 13"
        assert snapshot["file_count"] == 2
        assert snapshot["total_size_bytes"] == 41
        assert snapshot["truncated_file_count"] == 0
        assert {item["file_name"] for item in snapshot["files"]} == {"Media 1.jpg", "Media 2.jpg"}
        assert {item["object_key"] for item in snapshot["files"]} == set(object_keys)

    assert client.post(f"/company-media/albums/{album_id}/restore").status_code == 302
    with app.app_context():
        restored = AuditLog.query.filter_by(action="company_media.album.restore", entity_id=album_id).one()
        assert restored.old_values_json["file_count"] == 2
        assert {item["file_name"] for item in restored.old_values_json["files"]} == {"Media 1.jpg", "Media 2.jpg"}


def test_denied_folder_and_album_archives_change_nothing_and_record_nothing(client, app):
    document_data = _document_folder_with_children(app)
    album_id, _file_ids, _object_keys = _album_with_files(app)
    with app.app_context():
        before = AuditLog.query.count()

    _login(client, "viewer")
    assert client.post(f"/project-documents/folders/{document_data['folder_id']}/archive").status_code == 403
    assert client.post(f"/company-media/albums/{album_id}/archive").status_code == 403

    with app.app_context():
        assert db.session.get(ProjectDocumentFolder, document_data["folder_id"]).is_active is True
        assert db.session.get(CompanyMediaAlbum, album_id).is_active is True
        assert AuditLog.query.count() == before


def test_company_and_partner_lifecycle_snapshots_include_creation_metadata(client, app):
    with app.app_context():
        super_admin = db.session.get(User, 1)
        company = Company(id=9901, name="Công ty snapshot lifecycle")
        partner = Partner(id=9902, full_name="Đối tác snapshot lifecycle", created_by_user_id=super_admin.id)
        db.session.add_all((company, partner))
        db.session.commit()
        company_id, partner_id = company.id, partner.id

    _login(client, "super")
    assert client.post(f"/partner-companies/{company_id}/archive").status_code == 302
    assert client.post(f"/partner-companies/{company_id}/restore").status_code == 302
    assert client.post(f"/partners/{partner_id}/archive").status_code == 302
    assert client.post(f"/partners/{partner_id}/restore").status_code == 302

    with app.app_context():
        company_archive = AuditLog.query.filter_by(action="company.archive", entity_id=company_id).one()
        company_restore = AuditLog.query.filter_by(action="company.restore", entity_id=company_id).one()
        assert company_archive.old_values_json["created_at"]
        assert company_restore.old_values_json["created_at"]
        partner_archive = AuditLog.query.filter_by(action="partner.archive", entity_id=partner_id).one()
        partner_restore = AuditLog.query.filter_by(action="partner.restore", entity_id=partner_id).one()
        assert partner_archive.old_values_json["created_by_id"] == 1
        assert partner_archive.old_values_json["created_at"]
        assert partner_restore.old_values_json["created_by_id"] == 1
        assert partner_restore.old_values_json["created_at"]


def test_denied_project_and_customer_archives_change_nothing_and_record_nothing(client, app):
    with app.app_context():
        super_admin = db.session.get(User, 1)
        project = Project(
            id=9903,
            code="P-AUDIT-DENIED",
            name="Dự án không được archive",
            status="active",
            created_by_user_id=super_admin.id,
        )
        customer = Customer(
            id=9904,
            name="Khách hàng không được archive",
            normalized_name="khách hàng không được archive",
            created_by_id=super_admin.id,
        )
        db.session.add_all((project, customer))
        db.session.commit()
        project_id, customer_id = project.id, customer.id
        before = AuditLog.query.count()

    _login(client, "viewer")
    assert client.post(f"/admin/projects/{project_id}/archive").status_code == 403
    assert client.post(f"/customers/{customer_id}/archive").status_code == 403

    with app.app_context():
        assert db.session.get(Project, project_id).status == "active"
        assert db.session.get(Customer, customer_id).is_active is True
        assert AuditLog.query.count() == before
