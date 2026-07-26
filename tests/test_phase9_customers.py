import importlib.util
from datetime import date
from pathlib import Path

import sqlalchemy as sa
from alembic import op
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext

from app.extensions import db
from app.models import Customer, DailyReport, Permission, Project, ProjectUser, ReportCategory, Role, RolePermission, User


def login(client, username, password="password123"):
    return client.post("/login", data={"username_or_email": username, "password": password})


def _grant(app, username, *codes):
    with app.app_context():
        user = User.query.filter_by(username=username).one()
        permissions = Permission.query.filter(Permission.code.in_(codes)).all()
        db.session.add_all(RolePermission(role_id=user.role_id, permission_id=permission.id) for permission in permissions)
        db.session.commit()


def _customer(app, name):
    with app.app_context():
        customer = Customer(name=name, normalized_name=name.casefold(), is_active=True)
        db.session.add(customer)
        db.session.commit()
        return customer.id


def _assign_customer(app, customer_id, *project_ids):
    with app.app_context():
        for project_id in project_ids:
            db.session.get(Project, project_id).customer_id = customer_id
        db.session.commit()


def test_customer_normalization_and_archive_preserves_project_history(client, app):
    login(client, "super")
    created = client.post("/customers/new", data={"name": "  Geleximco   Group ", "description": "Owner"})
    assert created.status_code == 302

    with app.app_context():
        customer = Customer.query.filter_by(normalized_name="geleximco group").one()
        project = db.session.get(Project, 1)
        project.customer_id = customer.id
        db.session.add(DailyReport(
            id=701,
            project_id=project.id,
            report_date=date(2026, 7, 26),
            overall_status="GOOD",
            highlight="Preserved customer archive regression",
            created_by_user_id=1,
        ))
        db.session.commit()
        customer_id = customer.id

    duplicate = client.post("/customers/new", data={"name": "geleximco group"})
    assert duplicate.status_code == 400

    archived = client.post(f"/customers/{customer_id}/archive")
    assert archived.status_code == 302
    with app.app_context():
        assert db.session.get(Customer, customer_id).is_active is False
        assert db.session.get(Project, 1).customer_id == customer_id
        assert DailyReport.query.filter_by(id=701).count() == 1
        assert ProjectUser.query.filter_by(project_id=1, user_id=3).count() == 1
        assert ReportCategory.query.filter_by(project_id=1).count() == 2


def test_move_project_preserves_reports_memberships_and_categories(client, app):
    source_id = _customer(app, "Khách hàng chưa phân loại")
    _assign_customer(app, source_id, 1, 2)
    target_id = _customer(app, "Handico")
    with app.app_context():
        db.session.add(DailyReport(
            id=702,
            project_id=1,
            report_date=date(2026, 7, 27),
            overall_status="UPDATED",
            highlight="Move customer regression",
            created_by_user_id=1,
        ))
        db.session.commit()

    login(client, "super")
    moved = client.post(
        f"/customers/{source_id}/projects/1/move",
        data={"target_customer_id": str(target_id)},
    )
    assert moved.status_code == 302
    with app.app_context():
        assert db.session.get(Project, 1).customer_id == target_id
        assert DailyReport.query.filter_by(id=702, project_id=1).count() == 1
        assert ProjectUser.query.filter_by(project_id=1, user_id=3).count() == 1
        assert ReportCategory.query.filter_by(project_id=1).count() == 2


def test_customer_scope_hides_inaccessible_projects_and_read_only_cannot_post(client, app):
    customer_id = _customer(app, "Khách hàng chưa phân loại")
    _assign_customer(app, customer_id, 1, 2)
    _grant(app, "reporter", "customers.view")
    login(client, "reporter")
    page = client.get("/customers")
    assert page.status_code == 200
    detail = client.get(f"/customers/{customer_id}")
    assert detail.status_code == 200
    assert b"Assigned Project" in detail.data
    assert b"Other Project" not in detail.data
    assert client.post("/customers/new", data={"name": "Blocked"}).status_code == 403

    client.post("/logout")
    login(client, "viewer")
    assert client.get("/customers").status_code == 200
    assert client.post("/customers/new", data={"name": "Viewer blocked"}).status_code == 403


def test_custom_customer_role_requires_edit_permission_for_mutation(client, app):
    customer_id = _customer(app, "Custom role customer")
    with app.app_context():
        role = Role(id=100, code="CUSTOMER_VIEWER", name="Customer viewer", is_system=False)
        user = User(
            id=100,
            full_name="Customer custom",
            username="customer_custom",
            password_hash="not-used-by-this-test",
            role=role,
            legacy_role=role.code,
        )
        db.session.add_all([role, user])
        permissions = Permission.query.filter(Permission.code.in_((
            "modules.reports.access", "customers.view", "projects.scope_all",
        ))).all()
        db.session.add_all(RolePermission(role_id=role.id, permission_id=permission.id) for permission in permissions)
        db.session.commit()

    with client.session_transaction() as session:
        session["_user_id"] = "100"
        session["_fresh"] = True
    assert client.get(f"/customers/{customer_id}").status_code == 200
    assert client.post(f"/customers/{customer_id}/edit", data={"name": "Blocked edit"}).status_code == 403

    with app.app_context():
        role = db.session.get(Role, 100)
        permission = Permission.query.filter_by(code="customers.edit").one()
        db.session.add(RolePermission(role_id=role.id, permission_id=permission.id))
        db.session.commit()

    edited = client.post(f"/customers/{customer_id}/edit", data={"name": "Allowed edit"})
    assert edited.status_code == 302
    with app.app_context():
        assert db.session.get(Customer, customer_id).name == "Allowed edit"


def test_customer_migration_backfills_populated_projects_idempotently():
    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    sa.Table("users", metadata, sa.Column("id", sa.Integer, primary_key=True))
    projects = sa.Table(
        "projects",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(projects.insert(), [
            {"id": 1, "code": "P001", "name": "Legacy one"},
            {"id": 2, "code": "P002", "name": "Legacy two"},
        ])
        context = MigrationContext.configure(connection)
        operations = Operations(context)
        operations._install_proxy()
        try:
            path = Path("migrations/versions/aa468094da4f_add_customers_and_project_grouping.py")
            spec = importlib.util.spec_from_file_location("phase9_customer_migration", path)
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            migration.upgrade()
        finally:
            operations._remove_proxy()

        customer_rows = connection.execute(sa.text("SELECT id, normalized_name FROM customers")).all()
        project_customer_ids = connection.execute(sa.text("SELECT customer_id FROM projects ORDER BY id")).scalars().all()

    assert customer_rows == [(1, "khách hàng chưa phân loại")]
    assert project_customer_ids == [1, 1]
