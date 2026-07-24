def login(client, username, next_url=None):
    suffix = f"?next={next_url}" if next_url else ""
    return client.post(f"/login{suffix}", data={"username_or_email": username, "password": "password123"})


def test_login_lands_on_modules_for_project_member(client):
    response = login(client, "reporter")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/modules/")


def test_login_respects_safe_next_and_rejects_unsafe_next(client):
    assert login(client, "reporter", "/reports/projects").headers["Location"].endswith("/reports/projects")
    client.post("/logout")
    assert login(client, "reporter", "https://invalid.example").headers["Location"].endswith("/modules/")


def test_membership_page_lists_only_active_memberships_and_vietnamese_labels(client):
    login(client, "super")
    response = client.get("/admin/projects/1/memberships")
    assert response.status_code == 200
    assert "Thêm thành viên dự án".encode() in response.data
    assert "Tìm người dùng theo tên, tài khoản hoặc email".encode() in response.data
    assert "Người lập báo cáo".encode() in response.data
    assert "Xem báo cáo".encode() in response.data


def test_membership_rejects_zero_capabilities_and_deactivation_removes_access(client, app):
    login(client, "super")
    response = client.post("/admin/projects/1/memberships/1", data={"project_role_code": "PROJECT_VIEWER"})
    assert response.status_code == 400
    response = client.post("/admin/projects/1/memberships/1/deactivate")
    assert response.status_code == 302
    client.post("/logout"); login(client, "reporter")
    assert client.get("/reports/projects/1/dashboard").status_code == 403
