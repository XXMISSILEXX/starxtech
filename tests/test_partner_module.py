from app.extensions import db
from app.models import Company, CompanyDepartment, Partner, PartnerFieldDefinition, PartnerFieldValue, UserRole
from tests.test_auth_permissions import login


def test_multi_module_login_redirects_to_module_selection(client):
    response = login(client, "super")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/modules/")


def test_module_selection_sets_active_module_and_sidebar(client):
    login(client, "super")

    response = client.get("/modules/")
    assert response.status_code == 200
    assert "Báo cáo hàng ngày".encode() in response.data
    assert "Quản lý đối tác".encode() in response.data

    selected = client.get("/modules/select/partners")
    assert selected.status_code == 302
    assert selected.headers["Location"].endswith("/partners/dashboard")
    with client.session_transaction() as session:
        assert session["active_module"] == "partners"

    page = client.get("/partners/dashboard")
    assert "Tổng quan đối tác".encode() in page.data
    assert "Trường dữ liệu đối tác".encode() in page.data
    assert b"Made by Tran Hieu Slayer" in page.data
    assert "Báo cáo</span>".encode() not in page.data


def test_project_manager_can_create_partner_but_not_manage_fields(client, app):
    login(client, "pm")

    forbidden = client.get("/partner-fields/")
    assert forbidden.status_code == 403

    created = client.post(
        "/partner-companies/new",
        data={"name": "Acme", "industry": "Thi công", "is_active": "on"},
    )
    assert created.status_code == 302
    with app.app_context():
        company = Company.query.filter_by(name="Acme").one()
        company_id = company.id
    with app.app_context():
        department = CompanyDepartment(id=1000, company_id=company_id, name="Ban giám đốc", is_active=True)
        db.session.add(department)
        db.session.commit()
        department_id = department.id

    response = client.post(
        "/partners/new",
        data={"full_name": "Nguyen Van A", "company_id": str(company_id), "department_id": str(department_id), "position": "CEO"},
    )
    assert response.status_code == 302
    with app.app_context():
        assert Partner.query.filter_by(full_name="Nguyen Van A").first() is not None


def test_reporter_can_view_partners_but_cannot_write(client, app):
    with app.app_context():
        company = Company(id=1, name="View Co")
        partner = Partner(id=1, full_name="Read Only", company=company)
        db.session.add_all([company, partner])
        db.session.commit()

    login(client, "reporter")

    assert client.get("/partners/1").status_code == 200
    assert client.post("/partners/new", data={"full_name": "Blocked"}).status_code == 403
    assert client.get("/partner-fields/").status_code == 403


def test_field_definition_snapshot_survives_definition_edit_and_deactivate(client, app):
    login(client, "admin")

    created_field = client.post(
        "/partner-fields/new",
        data={
            "label": "Mức ưu tiên",
            "field_key": "priority",
            "field_type": "select",
            "group_name": "Phân loại",
            "options": "Cao\nThấp",
            "sort_order": "1",
            "is_active": "on",
        },
    )
    assert created_field.status_code == 302
    with app.app_context():
        db.session.add(Company(id=1, name="Snapshot Co"))
        db.session.add(CompanyDepartment(id=1, company_id=1, name="Ban giám đốc"))
        db.session.commit()

    created_partner = client.post(
        "/partners/new",
        data={
            "full_name": "Tran Thi B",
            "company_id": "1",
            "department_id": "1",
            "position": "Giám đốc",
            "fields[0][field_definition_id]": "1",
            "fields[0][value]": "Cao",
        },
    )
    assert created_partner.status_code == 302

    edited_field = client.post(
        "/partner-fields/1/edit",
        data={
            "label": "Ưu tiên mới",
            "field_key": "priority",
            "field_type": "text",
            "group_name": "Đã đổi",
            "sort_order": "1",
            "is_active": "on",
        },
    )
    assert edited_field.status_code == 302

    detail = client.get("/partners/1")
    assert "Mức ưu tiên".encode() in detail.data
    assert "Cao".encode() in detail.data
    assert "Ưu tiên mới".encode() not in detail.data

    deactivated = client.post("/partner-fields/1/deactivate")
    assert deactivated.status_code == 302
    new_form = client.get("/partners/new")
    assert "Ưu tiên mới".encode() not in new_form.data

    with app.app_context():
        value = PartnerFieldValue.query.one()
        assert value.field_label_snapshot == "Mức ưu tiên"
        assert value.field_type_snapshot == "select"


def test_validation_failure_preserves_core_and_dynamic_input(client):
    login(client, "admin")
    with client.application.app_context():
        db.session.add(Company(id=100, name="Validation Co"))
        db.session.add(CompanyDepartment(id=100, company_id=100, name="Ban giám đốc"))
        db.session.commit()
    client.post(
        "/partner-fields/new",
        data={
            "label": "Sở thích",
            "field_key": "hobby",
            "field_type": "text",
            "group_name": "Cá nhân",
            "sort_order": "1",
            "is_active": "on",
        },
    )

    response = client.post(
        "/partners/new",
        data={
            "full_name": "",
            "company_id": "100",
            "department_id": "100",
            "position": "Giám đốc",
            "fields[0][field_definition_id]": "1",
            "fields[0][value]": "Golf",
        },
    )

    assert response.status_code == 400
    assert "Giám đốc".encode() in response.data
    assert "Sở thích".encode() in response.data
    assert "Golf".encode() in response.data


def test_company_detail_groups_partners_by_department(client, app):
    with app.app_context():
        company = Company(id=1, name="Group Co", industry="Xây dựng")
        db.session.add_all(
            [
                company,
                Partner(id=1, full_name="Partner A", company=company, department="Kỹ thuật"),
                Partner(id=2, full_name="Partner B", company=company, department="Tài chính"),
            ]
        )
        db.session.commit()

    login(client, "super")
    response = client.get("/partner-companies/1")

    assert response.status_code == 200
    assert "Kỹ thuật".encode() in response.data
    assert "Partner A".encode() in response.data
    assert "Tài chính".encode() in response.data
