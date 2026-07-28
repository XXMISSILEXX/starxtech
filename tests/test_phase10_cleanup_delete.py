from datetime import date, datetime, timedelta

import pytest
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import (AuditLog, Permission, PersistentIssue, ProjectUser,
                        ReportAttachment, Role, RolePermission, StorageObject,
                        UploadBatch, UploadBatchItem, UploadSelectionSession,
                        User)
from app.reports import direct_uploads
from tests.test_reports_attachments import direct_report, login


def _grant(app, username, code):
    with app.app_context():
        user = User.query.filter_by(username=username).one()
        permission = Permission.query.filter_by(code=code).one()
        db.session.add(RolePermission(role_id=user.role_id, permission_id=permission.id))
        db.session.commit()


def _session_with_object(app, username, project_id, *, status=None, expires_at=None):
    with app.app_context():
        user = User.query.filter_by(username=username).one()
        session_id = direct_uploads.create_session(
            user=user, project_id=project_id, declared_files=1, declared_size_bytes=1,
        )["upload_session_id"]
        presigned = direct_uploads.presign(
            user=user,
            project_id=project_id,
            session_id=session_id,
            files=[{
                "client_file_id": f"file-{session_id}",
                "client_section_id": f"section-{session_id}",
                "filename": f"{session_id}.jpg",
                "mime_type": "image/jpeg",
                "size": 1,
            }],
        )
        object_id = presigned["items"][0]["storage_object_id"]
        storage = db.session.get(StorageObject, object_id)
        app.extensions["storage_provider"].put_bytes(
            storage.bucket, storage.object_key, b"x", storage.mime_type,
        )
        session = db.session.get(UploadSelectionSession, session_id)
        if status:
            session.status = status
        if expires_at:
            session.expires_at = expires_at
        db.session.commit()
        return session_id, object_id, (storage.bucket, storage.object_key)


@pytest.mark.parametrize("path, is_v2", [
    ("/reports/projects/1/reports/upload-sessions/{session_id}/cancel", False),
    ("/api/projects/1/daily-reports/upload-sessions/{session_id}/cancel", True),
])
def test_single_session_cancel_isolated_for_legacy_and_v2(client, app, path, is_v2):
    own_session_id, own_object_id, own_key = _session_with_object(app, "reporter", 1)
    other_project_id, other_project_object_id, other_project_key = _session_with_object(
        app, "super", 2, status="cancelled",
    )
    other_user_id, other_user_object_id, other_user_key = _session_with_object(
        app, "pm", 1, status="expired", expires_at=datetime.utcnow() - timedelta(minutes=1),
    )

    assert login(client, "reporter").status_code == 302
    response = client.post(path.format(session_id=own_session_id))

    assert response.status_code == 200, response.get_data(as_text=True)
    body = response.get_json()
    cleanup = body["data"]["cleanup"] if is_v2 else body["cleanup"]
    assert cleanup["complete"] is True
    with app.app_context():
        provider = app.extensions["storage_provider"]
        assert db.session.get(StorageObject, own_object_id) is None
        assert own_key not in provider.objects
        for object_id, key, session_id in (
            (other_project_object_id, other_project_key, other_project_id),
            (other_user_object_id, other_user_key, other_user_id),
        ):
            assert db.session.get(StorageObject, object_id) is not None
            assert key in provider.objects
            assert db.session.get(UploadSelectionSession, session_id) is not None


def test_single_session_cancel_is_idempotent(client, app):
    session_id, object_id, key = _session_with_object(app, "reporter", 1)
    assert login(client, "reporter").status_code == 302
    url = f"/api/projects/1/daily-reports/upload-sessions/{session_id}/cancel"
    assert client.post(url).status_code == 200
    repeated = client.post(url)
    assert repeated.status_code == 200
    assert repeated.get_json()["data"]["cleanup"]["complete"] is True
    with app.app_context():
        assert db.session.get(StorageObject, object_id) is None
        assert key not in app.extensions["storage_provider"].objects


def test_single_session_cancel_rejects_cross_project_and_non_owner(client, app):
    session_id, object_id, key = _session_with_object(app, "reporter", 1)
    assert login(client, "super").status_code == 302
    mismatch = client.post(f"/api/projects/2/daily-reports/upload-sessions/{session_id}/cancel")
    assert mismatch.status_code == 403
    client.post("/logout")
    assert login(client, "pm").status_code == 302
    non_owner = client.post(f"/reports/projects/1/reports/upload-sessions/{session_id}/cancel")
    assert non_owner.status_code == 403
    with app.app_context():
        assert db.session.get(StorageObject, object_id) is not None
        assert key in app.extensions["storage_provider"].objects


def test_cancel_never_removes_finalized_report_attachment(client, app):
    assert login(client, "reporter").status_code == 302
    result = direct_report(client, app)
    session_id = result["upload_session_id"]
    with app.app_context():
        attachment = ReportAttachment.query.one()
        object_id = attachment.storage_object_id
        storage = db.session.get(StorageObject, object_id)
        key = storage.bucket, storage.object_key

    response = client.post(f"/api/projects/1/daily-reports/upload-sessions/{session_id}/cancel")
    assert response.status_code == 409
    with app.app_context():
        assert db.session.get(ReportAttachment, attachment.id) is not None
        assert db.session.get(StorageObject, object_id) is not None
        assert key in app.extensions["storage_provider"].objects


def test_cancel_reports_incomplete_when_session_object_is_already_referenced(client, app):
    assert login(client, "reporter").status_code == 302
    report_result = direct_report(client, app, files=[])
    session_id, object_id, key = _session_with_object(app, "reporter", 1)
    with app.app_context():
        section_id = report_result["sections"][0].id
        db.session.add(ReportAttachment(
            id=9601,
            daily_report_section_id=section_id,
            original_filename="shared.jpg",
            storage_object_id=object_id,
            mime_type="image/jpeg",
            file_size=1,
            uploaded_by_user_id=3,
        ))
        db.session.commit()

    response = client.post(f"/api/projects/1/daily-reports/upload-sessions/{session_id}/cancel")
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "upload_session_cleanup_incomplete"
    with app.app_context():
        assert db.session.get(StorageObject, object_id) is not None
        assert key in app.extensions["storage_provider"].objects
        assert UploadBatchItem.query.join(UploadBatch).filter(
            UploadBatch.selection_session_id == session_id,
        ).count() == 1


def test_trusted_global_cleanup_still_cleans_expired_session(app):
    session_id, object_id, key = _session_with_object(
        app, "reporter", 1, expires_at=datetime.utcnow() - timedelta(minutes=1),
    )
    with app.app_context():
        summary = direct_uploads.cleanup_expired_sessions(dry_run=False, batch_size=1)
        assert summary == {"matched": 1, "cleaned": 1, "partial": 0, "failed": 0, "dry_run": False}
        assert db.session.get(UploadSelectionSession, session_id).status == "expired"
        assert db.session.get(StorageObject, object_id) is None
        assert key not in app.extensions["storage_provider"].objects


def test_attachment_delete_requires_dangerous_permission_and_preserves_bytes(client, app):
    assert login(client, "reporter").status_code == 302
    direct_report(client, app)
    with app.app_context():
        attachment = ReportAttachment.query.one()
        attachment_id, object_id = attachment.id, attachment.storage_object_id
        storage = db.session.get(StorageObject, object_id)
        key = storage.bucket, storage.object_key

    denied = client.post(f"/attachments/{attachment_id}/delete")
    assert denied.status_code == 403
    with app.app_context():
        assert db.session.get(ReportAttachment, attachment_id) is not None
        assert db.session.get(StorageObject, object_id) is not None
        assert key in app.extensions["storage_provider"].objects
        assert AuditLog.query.filter_by(action="attachment.delete", entity_id=attachment_id).count() == 0


def test_attachment_delete_grant_without_parent_scope_is_denied(client, app):
    assert login(client, "reporter").status_code == 302
    direct_report(client, app)
    with app.app_context():
        attachment = ReportAttachment.query.one()
        role = Role(id=9501, code="PHASE10_ATTACHMENT_DELETE", name="Phase 10 attachment delete", is_system=False)
        actor = User(
            id=9501,
            full_name="Attachment only",
            username="attachment-only",
            email="attachment-only@example.com",
            password_hash=generate_password_hash("password123"),
            role=role,
            legacy_role=role.code,
        )
        db.session.add_all([role, actor])
        db.session.flush()
        for code in ("modules.reports.access", "report_attachments.delete"):
            db.session.add(RolePermission(role_id=role.id, permission_id=Permission.query.filter_by(code=code).one().id))
        db.session.commit()
        attachment_id, object_id = attachment.id, attachment.storage_object_id
        storage = db.session.get(StorageObject, object_id)
        key = storage.bucket, storage.object_key

    client.post("/logout")
    assert login(client, "attachment-only").status_code == 302
    assert client.post(f"/attachments/{attachment_id}/delete").status_code == 403
    with app.app_context():
        assert db.session.get(ReportAttachment, attachment_id) is not None
        assert key in app.extensions["storage_provider"].objects


def test_attachment_delete_rejects_cross_project_id_substitution(client, app):
    _grant(app, "reporter", "report_attachments.delete")
    assert login(client, "super").status_code == 302
    direct_report(client, app, project_id=2, category_id=3)
    with app.app_context():
        attachment = ReportAttachment.query.one()
        attachment_id, object_id = attachment.id, attachment.storage_object_id
        storage = db.session.get(StorageObject, object_id)
        key = storage.bucket, storage.object_key
    client.post("/logout")
    assert login(client, "reporter").status_code == 302
    assert client.post(f"/attachments/{attachment_id}/delete").status_code == 403
    with app.app_context():
        assert db.session.get(ReportAttachment, attachment_id) is not None
        assert db.session.get(StorageObject, object_id) is not None
        assert key in app.extensions["storage_provider"].objects


def _issue(app, *, project_id=1, title="Phase 10 issue"):
    with app.app_context():
        issue = PersistentIssue(
            id=9501,
            project_id=project_id,
            title=title,
            severity="HIGH",
            status="OPEN",
            opened_date=date(2026, 7, 28),
            created_by_user_id=1,
        )
        db.session.add(issue)
        db.session.commit()
        return issue.id


def test_issue_delete_requires_dangerous_permission_but_not_edit_or_reopen(client, app):
    issue_id = _issue(app)
    assert login(client, "pm").status_code == 302
    assert client.post(f"/reports/issues/{issue_id}/edit", data={
        "title": "Edited without delete grant", "description": "x", "severity": "HIGH",
        "status": "OPEN", "opened_date": "2026-07-28", "due_date": "", "owner_user_id": "",
    }).status_code == 302
    assert client.post(f"/reports/issues/{issue_id}/close").status_code == 302
    assert client.post(f"/reports/issues/{issue_id}/reopen").status_code == 302
    assert client.post(f"/reports/issues/{issue_id}/delete").status_code == 403
    with app.app_context():
        assert db.session.get(PersistentIssue, issue_id).deleted_at is None
        assert AuditLog.query.filter_by(action="issue.delete", entity_id=issue_id).count() == 0


def test_issue_delete_grant_without_issue_scope_is_denied(client, app):
    issue_id = _issue(app)
    _grant(app, "reporter", "issues.delete")
    assert login(client, "reporter").status_code == 302
    assert client.post(f"/reports/issues/{issue_id}/delete").status_code == 403
    with app.app_context():
        assert db.session.get(PersistentIssue, issue_id).deleted_at is None


def test_issue_delete_with_scope_and_grant_soft_deletes_and_audits(client, app):
    issue_id = _issue(app)
    _grant(app, "pm", "issues.delete")
    assert login(client, "pm").status_code == 302
    assert client.post(f"/reports/issues/{issue_id}/delete").status_code == 302
    with app.app_context():
        assert db.session.get(PersistentIssue, issue_id).deleted_at is not None
        assert AuditLog.query.filter_by(action="issue.delete", entity_id=issue_id).count() == 1
