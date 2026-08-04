from flask_login import AnonymousUserMixin
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import Permission, Role, RolePermission, User
from app.modules.services import get_accessible_modules


def _login(client, username):
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def _create_user_with_permissions(app, *, user_id, username, codes):
    with app.app_context():
        role = Role(id=user_id, code=f"TEST_{username.upper()}", name=username, is_system=False)
        user = User(
            id=user_id,
            username=username,
            email=f"{username}@example.com",
            full_name=username,
            password_hash=generate_password_hash("password123"),
            role=role,
            legacy_role=role.code,
            is_active=True,
        )
        db.session.add(user)
        db.session.flush()
        permissions = Permission.query.filter(Permission.code.in_(codes)).all()
        assert {permission.code for permission in permissions} == set(codes)
        db.session.add_all(RolePermission(role_id=role.id, permission_id=permission.id) for permission in permissions)
        db.session.commit()
        return user.id


def _module_cards(app, user_id=None):
    with app.app_context():
        user = db.session.get(User, user_id) if user_id is not None else AnonymousUserMixin()
        with app.test_request_context("/modules/"):
            return get_accessible_modules(user)


def test_projects_view_does_not_expose_system_administration_module(client, app):
    _create_user_with_permissions(app, user_id=101, username="projects-only", codes=("projects.view",))

    _login(client, "projects-only")

    page = client.get("/modules/")
    assert b'data-module-card="admin"' not in page.data
    assert client.get("/modules/select/admin").status_code == 403


def test_roles_view_exposes_system_administration_module_and_opens_roles(client, app):
    _create_user_with_permissions(app, user_id=102, username="roles-only", codes=("roles.view",))

    _login(client, "roles-only")

    page = client.get("/modules/")
    assert b'data-module-card="admin"' in page.data
    selected = client.get("/modules/select/admin")
    assert selected.status_code == 302
    assert selected.headers["Location"].endswith("/admin/roles")
    assert client.get("/modules/select/admin", follow_redirects=True).status_code == 200


def test_select_admin_uses_the_first_permitted_admin_destination(client, app):
    cases = (
        (103, "users-only", ("users.view",), "/admin/users"),
        (104, "roles-then-branding", ("roles.view", "settings.branding.view"), "/admin/roles"),
        (105, "storage-only", ("storage.dashboard.view",), "/admin/storage/"),
        (106, "branding-only", ("settings.branding.view",), "/admin/branding"),
    )
    for user_id, username, codes, destination in cases:
        _create_user_with_permissions(app, user_id=user_id, username=username, codes=codes)
        _login(client, username)
        response = client.get("/modules/select/admin")
        assert response.status_code == 302
        assert response.headers["Location"].endswith(destination)
        assert client.get("/modules/select/admin", follow_redirects=True).status_code == 200
        client.post("/logout")


def test_every_accessible_module_card_avoids_forbidden_for_representative_users(client, app):
    _create_user_with_permissions(app, user_id=107, username="projects-card", codes=("projects.view",))
    _create_user_with_permissions(app, user_id=108, username="roles-card", codes=("roles.view",))
    _create_user_with_permissions(app, user_id=109, username="branding-card", codes=("settings.branding.view",))

    representatives = (
        ("anonymous", None, None),
        ("projects.view only", 107, "projects-card"),
        ("roles.view only", 108, "roles-card"),
        ("settings.branding.view only", 109, "branding-card"),
        ("ADMIN", 6, "admin"),
        ("VIEWER_ADMIN", 2, "viewer"),
        ("SUPER_ADMIN", 1, "super"),
    )
    for label, user_id, username in representatives:
        cards = _module_cards(app, user_id)
        if username:
            _login(client, username)
        for card in cards:
            response = client.get(card["url"], follow_redirects=True)
            assert response.status_code != 403, f"{label}: {card['key']} ({card['url']}) returned 403"
            assert all(item.status_code != 403 for item in response.history)
        if username:
            client.post("/logout")


def test_403_and_404_use_vietnamese_application_error_pages(client, app):
    _create_user_with_permissions(app, user_id=110, username="denied", codes=("projects.view",))
    _login(client, "denied")

    forbidden = client.get("/modules/select/admin")
    assert forbidden.status_code == 403
    assert "Bạn không có quyền truy cập trang này".encode() in forbidden.data
    assert b'href="/modules/"' in forbidden.data
    assert b"projects.view" not in forbidden.data
    assert b"Forbidden" not in forbidden.data
    assert b"app-shell" in forbidden.data

    missing = client.get("/duong-dan-khong-ton-tai")
    assert missing.status_code == 404
    assert "Trang bạn tìm kiếm không tồn tại".encode() in missing.data
    assert b'href="/modules/"' in missing.data
    assert b"app-shell" in missing.data
