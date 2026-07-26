def login(client, username_or_email, password="password123"):
    return client.post(
        "/login",
        data={
            "username_or_email": username_or_email,
            "password": password,
        },
    )


def test_mobile_account_actions_are_in_offcanvas_and_topbar_is_mobile_hidden(client):
    login(client, "super")

    response = client.get("/reports/dashboard/system")

    assert response.status_code == 200
    assert b'class="topbar-actions mobile-hide"' in response.data
    assert b'id="mobileSidebar"' in response.data
    assert "Cài đặt cá nhân".encode() in response.data
    assert b'data-testid="mobile-account-settings-link"' in response.data
    assert b'href="/account/"' in response.data
    assert "Đăng xuất".encode() in response.data
    assert b'data-bs-target="#accountInfoModal"' not in response.data
    assert b'id="accountInfoModal"' not in response.data
    assert b'href="/change-password"' not in response.data
    assert "Super".encode() in response.data
    assert b"super@example.com" in response.data
    assert b'mobile-logout-form' in response.data
