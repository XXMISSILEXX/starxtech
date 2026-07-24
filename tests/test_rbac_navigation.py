from app.extensions import db
from app.models import Permission, RolePermission, User


def login(client, username, password="password123"):
    return client.post("/login", data={"username_or_email": username, "password": password})


def test_roles_navigation_visibility_and_access(client, app):
    login(client, "super")
    response = client.get("/reports/dashboard")
    assert response.status_code == 200
    assert b"Vai tr\xc3\xb2 & ph\xc3\xa2n quy\xe1\xbb\x81n" not in response.data
    assert b'href="/admin/roles"' not in response.data
    modules = client.get("/modules/")
    assert b"Qu\xe1\xba\xa3n tr\xe1\xbb\x8b h\xe1\xbb\x87 th\xe1\xbb\x91ng" in modules.data
    assert b'href="/modules/select/admin"' in modules.data
    assert client.get("/modules/select/admin").status_code == 302
    roles_page = client.get("/admin/roles")
    assert roles_page.status_code == 200
    assert b"Vai tr\xc3\xb2 & ph\xc3\xa2n quy\xe1\xbb\x81n" in roles_page.data
    assert b"B\xe1\xba\xa3ng \xc4\x91i\xe1\xbb\x81u khi\xe1\xbb\x83n" not in roles_page.data

    client.post("/logout")
    login(client, "admin")
    assert client.get("/admin/roles").status_code == 403

    with app.app_context():
        permission = Permission.query.filter_by(code="roles.view").first()
        if permission is None:
            permission = Permission(
                code="roles.view",
                name="Xem vai tro",
                description="Xem vai tro",
                module="roles",
                group_name="Vai tro",
                action="view",
                resource="roles",
            )
            db.session.add(permission)
            db.session.flush()
        admin = User.query.filter_by(username="admin").one()
        grant = RolePermission.query.filter_by(role_id=admin.role_id, permission_id=permission.id).first()
        if grant is None:
            db.session.add(RolePermission(role_id=admin.role_id, permission_id=permission.id))
        db.session.commit()

    client.post("/logout")
    login(client, "admin")
    assert "Quản trị hệ thống".encode() in client.get("/modules/").data
    response = client.get("/reports/dashboard")
    assert b"Vai tr\xc3\xb2 & ph\xc3\xa2n quy\xe1\xbb\x81n" not in response.data
    assert client.get("/admin/roles").status_code == 200
