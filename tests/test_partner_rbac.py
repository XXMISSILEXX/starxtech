from app.extensions import db
from app.models import Company, Partner, Permission, RolePermission, User
from tests.test_auth_permissions import login


def grant(app, username, *codes):
    with app.app_context():
        user = User.query.filter_by(username=username).one()
        permissions = Permission.query.filter(Permission.code.in_(codes)).all()
        db.session.add_all(RolePermission(role_id=user.role_id, permission_id=permission.id) for permission in permissions)
        db.session.commit()


def test_manual_partner_view_grant_is_read_only(client, app):
    grant(app, "reporter", "modules.partners.access", "partners.view")
    with app.app_context():
        db.session.add_all([Company(id=501, name="Read Co"), Partner(id=501, full_name="Read Partner", company_id=501)])
        db.session.commit()

    login(client, "reporter")
    assert client.get("/modules/select/partners").status_code == 302
    assert client.get("/partners/").status_code == 200
    assert client.get("/partners/501").status_code == 200
    assert client.get("/partners/new").status_code == 403
    assert client.post("/partners/new", data={"full_name": "Blocked"}).status_code == 403


def test_partner_module_is_denied_without_access_grant(client):
    login(client, "reporter")
    assert client.get("/modules/select/partners").status_code == 403
    assert client.get("/partners/").status_code == 403
