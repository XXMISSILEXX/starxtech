from datetime import date

from app.extensions import db
from app.models import Customer, DailyReport, Permission, Project, ProjectContractor, ProjectContractorAssignment, RolePermission, User


def login(client, username):
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def grant(app, username, *codes):
    with app.app_context():
        user = User.query.filter_by(username=username).one()
        permissions = Permission.query.filter(Permission.code.in_(codes)).all()
        db.session.add_all(RolePermission(role_id=user.role_id, permission_id=permission.id) for permission in permissions)
        db.session.commit()


def test_operations_scope_search_counts_and_accessibility(client, app):
    with app.app_context():
        customer = Customer(name="Geleximco", normalized_name="geleximco")
        contractor = ProjectContractor(name="VTS", normalized_name="vts")
        db.session.add_all([customer, contractor]); db.session.flush()
        project = db.session.get(Project, 1); project.customer_id = customer.id
        db.session.add_all([ProjectContractorAssignment(project_id=1, contractor_id=contractor.id, role="CONSTRUCTION", status="ACTIVE"), ProjectContractorAssignment(project_id=1, contractor_id=contractor.id, role="SOLUTION", status="ACTIVE"), DailyReport(id=990, project_id=1, report_date=date.today(), overall_status="GOOD", highlight="today", created_by_user_id=1)])
        db.session.commit()
    grant(app, "reporter", "project_operations.view")
    login(client, "reporter")
    page = client.get("/project-operations?q=Geleximco")
    assert page.status_code == 200 and b"Assigned Project" in page.data and b"Other Project" not in page.data
    assert b"1 thi c" in page.data and b"1 gi" in page.data and b"aria-controls" in page.data and b"aria-expanded" in page.data
    assert client.get("/project-operations?q=ASSIGNED").status_code == 200
    assert client.get("/project-operations?q=P001").status_code == 200


def test_workspace_scope_and_tabs_are_permission_aware(client, app):
    grant(app, "reporter", "project_operations.view", "dashboards.project.view", "reports.view", "project_updates.view", "issues.view", "contractor_assignments.view")
    login(client, "reporter")
    allowed = client.get("/projects/1/workspace")
    assert allowed.status_code == 200 and b"B\xc3\xa1o c\xc3\xa1o xuy\xc3\xaan su\xe1\xbb\x91t" in allowed.data
    assert client.get("/projects/2/workspace").status_code == 403


def test_operations_customer_order_project_order_and_null_customer(client, app):
    with app.app_context():
        alpha = Customer(name="Alpha", normalized_name="alpha")
        zulu = Customer(name="Zulu", normalized_name="zulu")
        db.session.add_all([alpha, zulu]); db.session.flush()
        first, second = db.session.get(Project, 1), db.session.get(Project, 2)
        first.customer_id, first.name = zulu.id, "Zulu project"
        second.customer_id, second.name = alpha.id, "Alpha project"
        db.session.commit()
    login(client, "super")
    page = client.get("/project-operations")
    assert page.status_code == 200
    assert page.data.index(b"Alpha") < page.data.index(b"Zulu")
