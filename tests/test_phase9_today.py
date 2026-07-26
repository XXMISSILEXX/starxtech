from datetime import datetime

from app.extensions import db
from app.models import DailyReport, Permission, RolePermission, User


def _grant(app, username, *codes):
    with app.app_context():
        user = User.query.filter_by(username=username).one()
        permissions = Permission.query.filter(Permission.code.in_(codes)).all()
        db.session.add_all(RolePermission(role_id=user.role_id, permission_id=permission.id) for permission in permissions)
        db.session.commit()


def test_today_is_scoped_and_routes_submitted_or_missing(client, app):
    _grant(app, "reporter", "reports.today.view")
    with app.app_context():
        db.session.add(DailyReport(id=991, project_id=1, report_date=datetime.now().date(), overall_status="GOOD", highlight="today", created_by_user_id=1)); db.session.commit()
    client.post("/login", data={"username_or_email": "reporter", "password": "password123"})
    page = client.get("/reports/today")
    assert page.status_code == 200
    assert b"Assigned Project" in page.data and b"Other Project" not in page.data and b"\xc4\x90\xc3\xa3 n\xe1\xbb\x99p" in page.data


def test_today_empty_scope_is_200_and_direct_permission_is_enforced(client):
    client.post("/login", data={"username_or_email": "reporter", "password": "password123"})
    assert client.get("/reports/today").status_code == 403
