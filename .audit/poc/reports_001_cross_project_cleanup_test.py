"""Secure regression for REPORTS-001: cancellation must not clean another project."""

from datetime import datetime, timedelta

pytest_plugins = ("tests.conftest",)

from app.extensions import db
from app.models import StorageObject, UploadBatch, UploadBatchItem, UploadSelectionSession, User
from app.reports.direct_uploads import create_session
from app.storage.providers import get_storage_provider


def _login(client, username):
    # The shared TestConfig disables CSRF, which is the repository's normal test convention.
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def test_cancelling_own_session_does_not_delete_other_project_upload_object(client, app):
    with app.app_context():
        reporter = User.query.filter_by(username="reporter").one()
        super_admin = User.query.filter_by(username="super").one()
        own_session_id = create_session(
            user=reporter, project_id=1, declared_files=1, declared_size_bytes=1
        )["upload_session_id"]
        target_session = UploadSelectionSession(
            id=9103,
            module_type="daily_reports",
            target_type="project",
            target_id=2,
            created_by_id=super_admin.id,
            declared_files=1,
            declared_size_bytes=1,
            status="cancelled",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        db.session.add(target_session)
        db.session.flush()
        target_object = StorageObject(
            id=9103,
            bucket="audit-poc",
            object_key="daily-reports/originals/unrelated-project.jpg",
            original_filename="unrelated-project.jpg",
            mime_type="image/jpeg",
            file_ext="jpg",
            file_size=1,
            storage_module="daily-reports",
            uploaded_by_id=super_admin.id,
            upload_status="pending",
        )
        target_batch = UploadBatch(
            id=9103,
            module_type="daily_reports",
            target_type="project",
            target_id=2,
            created_by_id=super_admin.id,
            selection_session_id=target_session.id,
            total_files=1,
            accepted_files=1,
            status="uploading",
        )
        db.session.add_all([target_object, target_batch])
        db.session.flush()
        db.session.add(UploadBatchItem(
            id=9103,
            upload_batch_id=target_batch.id,
            storage_object_id=target_object.id,
            client_file_id="other-project-file",
            client_section_id="other-project-section",
            original_filename=target_object.original_filename,
            mime_type=target_object.mime_type,
            file_size=target_object.file_size,
            status="accepted",
        ))
        provider = get_storage_provider()
        provider.put_bytes(target_object.bucket, target_object.object_key, b"x", target_object.mime_type)
        db.session.commit()
        target_object_id = target_object.id
        target_key = (target_object.bucket, target_object.object_key)

    assert _login(client, "reporter").status_code == 302
    response = client.post(f"/reports/projects/1/reports/upload-sessions/{own_session_id}/cancel")

    with app.app_context():
        db.session.expire_all()
        unrelated_object_survived = db.session.get(StorageObject, target_object_id) is not None
        unrelated_object_bytes_survived = target_key in get_storage_provider().objects

    secure = response.status_code == 200 and unrelated_object_survived and unrelated_object_bytes_survived
    assert secure, (
        "secure behavior may cancel the actor's own session but must retain the unrelated project-2 upload object; "
        f"got HTTP {response.status_code}, unrelated DB object survived={unrelated_object_survived}, "
        f"unrelated fake-storage bytes survived={unrelated_object_bytes_survived}"
    )
