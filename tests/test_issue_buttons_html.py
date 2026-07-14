from datetime import date

from app.extensions import db
from app.models import PersistentIssue


def login(client, username_or_email, password="password123"):
    return client.post(
        "/login",
        data={
            "username_or_email": username_or_email,
            "password": password,
        },
    )


def test_admin_sees_add_persistent_issue_button_on_empty_global_page(client):
    login(client, "super")

    response = client.get("/issues")

    assert response.status_code == 200
    assert "+ Thêm vấn đề tồn đọng".encode() in response.data
    assert "+ + Thêm vấn đề tồn đọng".encode() not in response.data
    assert b'href="/issues/new"' in response.data


def test_project_manager_sees_add_persistent_issue_button_on_empty_global_page(client):
    login(client, "pm")

    response = client.get("/issues")

    assert response.status_code == 200
    assert "+ Thêm vấn đề tồn đọng".encode() in response.data
    assert b'href="/issues/new"' in response.data


def test_empty_issue_page_still_has_add_cta(client):
    login(client, "super")

    response = client.get("/issues")

    assert response.status_code == 200
    assert "Không có vấn đề tồn đọng.".encode() in response.data
    assert response.data.count("+ Thêm vấn đề tồn đọng".encode()) >= 2
    assert "+ + Thêm vấn đề tồn đọng".encode() not in response.data


def test_reporter_does_not_see_delete_issue_button(client, app):
    with app.app_context():
        db.session.add(
            PersistentIssue(
                id=701,
                project_id=1,
                title="Reporter read-only delete check",
                severity="HIGH",
                status="OPEN",
                opened_date=date(2026, 7, 8),
                created_by_user_id=3,
                owner_user_id=3,
            )
        )
        db.session.commit()

    login(client, "reporter")
    response = client.get("/issues")

    assert response.status_code == 200
    assert "Xem chi tiết".encode() in response.data
    assert 'aria-label="Xem chi tiết"'.encode() in response.data
    assert b'class="action-label">Xem chi ti' in response.data
    assert "🟠 Cao".encode() in response.data
    assert "🟡 Đang mở".encode() in response.data
    assert b"/issues/701/delete" not in response.data


def test_persistent_issue_form_contains_icon_options(client):
    login(client, "super")

    response = client.get("/issues/new")

    assert response.status_code == 200
    assert "🟢 Thấp".encode() in response.data
    assert "🔴 Nghiêm trọng".encode() in response.data
    assert "🟡 Đang mở".encode() in response.data
    assert "🏗️".encode() in response.data
    assert "👤".encode() in response.data


def test_issue_create_missing_title_preserves_entered_data(client):
    login(client, "super")

    response = client.post(
        "/issues/new",
        data={
            "project_id": "1",
            "title": "",
            "description": "Mô tả vẫn phải được giữ lại.",
            "severity": "HIGH",
            "status": "PROCESSING",
            "opened_date": "2026-07-08",
            "due_date": "2026-07-15",
            "owner_user_id": "3",
        },
    )

    assert response.status_code == 400
    assert "Vui lòng nhập tiêu đề.".encode() in response.data
    assert "🏗️ P001 - Assigned Project".encode() in response.data
    assert "🟠 Cao".encode() in response.data
    assert "🔵 Đang xử lý".encode() in response.data
    assert "Mô tả vẫn phải được giữ lại.".encode() in response.data
