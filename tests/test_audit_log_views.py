from datetime import datetime, timedelta
from html import unescape

from sqlalchemy import text
from werkzeug.security import generate_password_hash

from app.audit import LEGACY_CONTENT_CREATE_ACTIONS, log_audit
from app.extensions import db
from app.models import AuditLog, Permission, Role, RolePermission, User


AUDIT_LIST_URL = "/admin/audit-log/"


def _login(client, username):
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def _grant(role_id, *codes):
    permissions = Permission.query.filter(Permission.code.in_(codes)).all()
    db.session.add_all(RolePermission(role_id=role_id, permission_id=item.id) for item in permissions)
    db.session.commit()


def _record(action="project.update", entity_type="Project", entity_id=1, *, actor_id=6, old_values=None, new_values=None, created_at=None):
    record = log_audit(action, entity_type, entity_id, old_values, new_values)
    record.actor_user_id = actor_id
    if created_at is not None:
        record.created_at = created_at
    db.session.flush()
    return record


def _audit_only_user():
    role = Role(code="AUDIT_ONLY", name="Chỉ xem lịch sử", is_system=False)
    db.session.add(role); db.session.flush()
    user = User(id=101, username="audit-only", email="audit-only@example.com", full_name="Audit Only",
                password_hash=generate_password_hash("password123"), role=role, legacy_role=role.code,
                is_active=True)
    db.session.add(user); db.session.flush()
    _grant(role.id, "audit_logs.view")
    return user


def test_audit_log_permissions_defaults_and_read_only_routes(client, app):
    with app.app_context():
        record = _record(); db.session.commit(); record_id = record.id
    assert client.get(AUDIT_LIST_URL).status_code == 302
    assert client.get(f"{AUDIT_LIST_URL}{record_id}").status_code == 302

    _login(client, "reporter")
    assert client.get(AUDIT_LIST_URL).status_code == 403
    assert client.get(f"{AUDIT_LIST_URL}{record_id}").status_code == 403
    client.post("/logout")

    _login(client, "viewer")
    assert client.get(AUDIT_LIST_URL).status_code == 403
    client.post("/logout")

    with app.app_context():
        viewer = db.session.get(User, 2)
        _grant(viewer.role_id, "audit_logs.view")
    _login(client, "viewer")
    assert client.get(AUDIT_LIST_URL).status_code == 200
    assert client.get(f"{AUDIT_LIST_URL}{record_id}").status_code == 200
    for method in (client.post, client.put, client.delete):
        assert method(AUDIT_LIST_URL).status_code == 405
        assert method(f"{AUDIT_LIST_URL}{record_id}").status_code == 405
    assert client.get(f"{AUDIT_LIST_URL}999999").status_code == 404
    client.post("/logout")

    _login(client, "admin")
    assert client.get(AUDIT_LIST_URL).status_code == 200
    client.post("/logout")
    _login(client, "super")
    assert client.get(AUDIT_LIST_URL).status_code == 200


def test_audit_only_role_can_enter_admin_and_sees_exactly_two_sidebar_links(client, app):
    with app.app_context():
        _audit_only_user()
    _login(client, "audit-only")
    selected = client.get("/modules/select/admin")
    assert selected.status_code == 302
    assert selected.headers["Location"].endswith(AUDIT_LIST_URL)
    page = client.get(selected.headers["Location"])
    assert page.status_code == 200
    assert page.data.count(AUDIT_LIST_URL.encode()) == 2
    assert "Quản trị".encode() in page.data


def test_audit_link_is_hidden_without_permission(client):
    _login(client, "reporter")
    page = client.get("/modules/")
    assert page.status_code == 200
    assert page.data.count(AUDIT_LIST_URL.encode()) == 0


def test_audit_list_filters_pagination_and_empty_messages(client, app):
    with app.app_context():
        start = datetime(2026, 8, 1, 8, 0)
        for index in range(21):
            _record("project.update", "Project", index + 1, created_at=start + timedelta(minutes=index))
        disclosure = _record("document.file.download", "ProjectDocumentFile", 90, created_at=start + timedelta(hours=2))
        db.session.commit()
        disclosure_id = disclosure.id
    _login(client, "admin")
    default_page = client.get(AUDIT_LIST_URL)
    assert default_page.status_code == 200
    assert b">document.file.download</a>" not in default_page.data
    assert "Tổng 21 bản ghi.".encode() in default_page.data
    page_two = client.get(f"{AUDIT_LIST_URL}?page=2&action=project.update")
    assert page_two.status_code == 200
    assert page_two.data.count(b">project.update</a>") == 1
    assert "Tổng 21 bản ghi.".encode() in page_two.data
    assert b"action=project.update" in page_two.data
    disclosure_page = client.get(f"{AUDIT_LIST_URL}?group=disclosure")
    assert disclosure_page.status_code == 200
    assert b"document.file.download" in disclosure_page.data
    assert "Lịch sử tải file trước đây".encode() in disclosure_page.data
    assert str(disclosure_id).encode() in disclosure_page.data
    no_match = client.get(f"{AUDIT_LIST_URL}?action=project.update&entity_type=ProjectDocumentFile")
    assert "Không có lịch sử thao tác nào khớp bộ lọc.".encode() in no_match.data

    with app.app_context():
        AuditLog.query.delete(); db.session.commit()
    empty = client.get(AUDIT_LIST_URL)
    assert "Chưa có lịch sử thao tác nào.".encode() in empty.data


def test_audit_pagination_uses_a_compact_window_and_preserves_filters(client, app):
    with app.app_context():
        start = datetime(2026, 8, 1, 8, 0)
        db.session.add_all(
            AuditLog(id=index + 1, actor_user_id=6, action="project.update", entity_type="Project",
                     entity_id=index + 1, created_at=start + timedelta(minutes=index))
            for index in range(1260)
        )
        db.session.commit()
    _login(client, "admin")
    page = client.get(f"{AUDIT_LIST_URL}?page=45&action=project.update")
    body = unescape(page.get_data(as_text=True))
    for number in (1, 43, 44, 46, 47, 63):
        assert f'href="{AUDIT_LIST_URL}?page={number}&hide_legacy_content_creates=1&action=project.update"' in body
    for number in (10, 55):
        assert f'href="{AUDIT_LIST_URL}?page={number}&hide_legacy_content_creates=1&action=project.update"' not in body
    assert "…" in body

    first = client.get(f"{AUDIT_LIST_URL}?action=project.update")
    assert 'aria-label="Trang trước" aria-disabled="true"'.encode() in first.data
    last = client.get(f"{AUDIT_LIST_URL}?page=63&action=project.update")
    assert 'aria-label="Trang sau" aria-disabled="true"'.encode() in last.data

    with app.app_context():
        AuditLog.query.delete(); _record(); db.session.commit()
    one_page = client.get(AUDIT_LIST_URL)
    assert 'aria-label="Phân trang"'.encode() not in one_page.data


def test_audit_hides_only_legacy_content_create_actions_by_default(client, app):
    with app.app_context():
        legacy_one = _record("company_media.file.create", "CompanyMediaFile", 1)
        legacy_two = _record("report.create", "DailyReport", 2)
        category = _record("category.create", "ReportCategory", 3)
        project = _record("project.create", "Project", 4)
        db.session.commit()
        legacy_ids = {legacy_one.id, legacy_two.id}
        retained_ids = {category.id, project.id}
    _login(client, "admin")
    default = client.get(AUDIT_LIST_URL)
    body = default.get_data(as_text=True)
    for action in LEGACY_CONTENT_CREATE_ACTIONS:
        assert f">{action}</a>" not in body
    assert ">category.create</a>" in body
    assert ">project.create</a>" in body
    assert "Tổng 2 bản ghi." in body
    assert "Đang ẩn 2 bản ghi tạo nội dung lịch sử" in body
    for record_id in legacy_ids:
        assert f"/admin/audit-log/{record_id}" not in body
    for record_id in retained_ids:
        assert f"/admin/audit-log/{record_id}" in body

    visible = client.get(f"{AUDIT_LIST_URL}?hide_legacy_content_creates=0")
    visible_body = visible.get_data(as_text=True)
    assert ">company_media.file.create</a>" in visible_body
    assert ">report.create</a>" in visible_body
    assert "Tổng 4 bản ghi." in visible_body
    assert "Đang ẩn" not in visible_body


def test_audit_detail_redacts_sensitive_snapshot_keys_and_handles_json_nulls(client, app):
    with app.app_context():
        record = _record(
            old_values={"object_key": "private/original.pdf", "password_hash": "hidden", "nested": {"Password": "nope", "API_KEY": "nope"}},
            new_values=None,
        )
        db.session.flush()
        sql_null_id = record.id + 1
        db.session.execute(text("""
            INSERT INTO audit_logs (id, action, entity_type, entity_id, old_values_json, new_values_json, created_at)
            VALUES (:id, 'project.update', 'Project', 2, NULL, 'null', CURRENT_TIMESTAMP)
        """), {"id": sql_null_id})
        db.session.commit()
        record_id = record.id
    _login(client, "admin")
    page = client.get(f"{AUDIT_LIST_URL}{record_id}")
    assert b"private/original.pdf" in page.data
    assert "••• đã che •••".encode() in page.data
    assert b"password_hash" in page.data
    assert b"Password" in page.data and b"API_KEY" in page.data
    assert b">hidden<" not in page.data and b">nope<" not in page.data
    assert "Không có trạng thái sau.".encode() in page.data
    sql_null_page = client.get(f"{AUDIT_LIST_URL}{sql_null_id}")
    assert sql_null_page.status_code == 200
    assert "Không có trạng thái trước.".encode() in sql_null_page.data
