"""Secure regression for AI-002: document view capability must not mint a download URL."""

pytest_plugins = ("tests.conftest",)

from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import (
    DownloadEvent,
    Project,
    ProjectDocumentFile,
    ProjectDocumentFolder,
    ProjectUser,
    Role,
    StorageObject,
    User,
)
from app.storage.providers import get_storage_provider


def _login(client, username):
    # The shared TestConfig disables CSRF, which is the repository's normal test convention.
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def test_document_viewer_without_download_permission_cannot_mint_signed_url(client, app):
    with app.app_context():
        role = Role(id=9104, code="AUDIT_DOCUMENT_VIEWER", name="Audit document viewer", is_system=False)
        actor = User(
            id=9104,
            full_name="Audit Document Viewer",
            username="audit-document-viewer",
            email="audit-document-viewer@example.com",
            password_hash=generate_password_hash("password123"),
            role=role,
            legacy_role=role.code,
        )
        admin = User.query.filter_by(username="admin").one()
        folder = ProjectDocumentFolder(
            id=9104,
            project_id=1,
            name="Audit download folder",
            is_root=False,
            root_type="project",
            created_by_id=admin.id,
        )
        db.session.add_all([role, actor, folder])
        db.session.flush()
        db.session.add(ProjectUser(
            id=9104,
            project_id=1,
            user_id=actor.id,
            project_role_code="CUSTOM",
            is_active=True,
            can_view_documents=True,
        ))
        storage = StorageObject(
            id=9104,
            bucket="audit-poc",
            object_key="document-library/originals/audit-download.pdf",
            original_filename="audit-download.pdf",
            mime_type="application/pdf",
            file_ext="pdf",
            file_size=1,
            storage_module="document-library",
            uploaded_by_id=admin.id,
            upload_status="active",
        )
        db.session.add(storage)
        db.session.flush()
        document_file = ProjectDocumentFile(
            id=9104,
            project_id=1,
            folder_id=folder.id,
            storage_object_id=storage.id,
            display_name="audit-download.pdf",
            created_by_id=admin.id,
        )
        db.session.add(document_file)
        get_storage_provider().put_bytes(storage.bucket, storage.object_key, b"x", storage.mime_type)
        db.session.commit()
        file_id = document_file.id
        download_events_before = DownloadEvent.query.count()

    assert _login(client, "audit-document-viewer").status_code == 302
    response = client.post(f"/project-documents/files/{file_id}/signed-download")

    with app.app_context():
        db.session.expire_all()
        download_events_after = DownloadEvent.query.count()

    signed_url = (response.get_json(silent=True) or {}).get("url")
    secure = (
        response.status_code in {400, 403, 404, 422}
        and not signed_url
        and download_events_after == download_events_before
    )
    assert secure, (
        "secure behavior must deny a project document viewer whose role has no project_document_files.download grant; "
        f"got HTTP {response.status_code}, signed URL minted={bool(signed_url)}, "
        f"download events before/after={download_events_before}/{download_events_after}"
    )
