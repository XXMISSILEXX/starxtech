import pytest

from app.extensions import db
from app.models import (
    Company,
    CompanyDepartment,
    Partner,
    PartnerFieldCollection,
    PartnerFieldDefinition,
    PartnerFieldValue,
    PartnerRelationship,
)
from app.partners.services import _add_with_sqlite_id
from tests.test_auth_permissions import login


def create_field(label="Sở thích", key="hobby", field_type="text", group="Cá nhân"):
    field = PartnerFieldDefinition(
        label=label,
        field_key=key,
        field_type=field_type,
        group_name=group,
        options_json=["A", "B"] if field_type in {"select", "multi_select"} else [],
        is_active=True,
    )
    _add_with_sqlite_id(field)
    field_id = field.id
    db.session.commit()
    return field_id


def create_company_department(company_id=900, company_name="Test Co", department_name="Ban giám đốc"):
    company = db.session.get(Company, company_id)
    if not company:
        company = Company(id=company_id, name=company_name)
        db.session.add(company)
    department = CompanyDepartment(
        id=company_id + 1000,
        company_id=company_id,
        name=department_name,
        is_active=True,
    )
    db.session.add(department)
    db.session.commit()
    return company.id, department.id


def test_company_detail_displays_company_note(client, app):
    with app.app_context():
        company = Company(id=100, name="Note Co", notes="Dòng 1\nDòng 2")
        db.session.add(company)
        db.session.commit()

    login(client, "super")
    response = client.get("/partner-companies/100")

    assert response.status_code == 200
    assert "Ghi chú".encode() in response.data
    assert "Dòng 1".encode() in response.data
    assert "Dòng 2".encode() in response.data


def test_create_company_department_with_parent_and_search(client, app):
    with app.app_context():
        company = Company(id=800, name="Department Co")
        parent = CompanyDepartment(id=1800, company=company, name="Ban giám đốc")
        db.session.add_all([company, parent])
        db.session.commit()

    login(client, "admin")
    created = client.post(
        "/partner-companies/800/departments/new",
        data={
            "name": "Kỹ thuật",
            "parent_department_id": "1800",
            "display_order": "2",
            "is_active": "on",
            "is_special_department": "on",
        },
    )
    assert created.status_code == 302
    with app.app_context():
        child = CompanyDepartment.query.filter_by(company_id=800, name="Kỹ thuật").one()
        assert child.parent_department_id == 1800
        assert child.is_special_department is True

    updated = client.post(
        f"/partner-companies/800/departments/{child.id}/edit",
        data={"name": "Kỹ thuật", "parent_department_id": "1800", "display_order": "2", "is_active": "on"},
    )
    assert updated.status_code == 302
    with app.app_context():
        assert db.session.get(CompanyDepartment, child.id).is_special_department is False

    search = client.get("/partner-companies/800/departments?q=Kỹ")
    assert search.status_code == 200
    assert "Kỹ thuật".encode() in search.data


@pytest.mark.parametrize("parent_value", ["", "0"])
def test_create_root_department_accepts_empty_parent_values(client, app, parent_value):
    with app.app_context():
        company = Company(id=810, name="Root Department Co")
        db.session.add(company)
        db.session.commit()

    login(client, "admin")
    response = client.post(
        "/partner-companies/810/departments/new",
        data={
            "name": f"Root {parent_value or 'empty'}",
            "parent_department_id": parent_value,
            "is_active": "on",
        },
    )

    assert response.status_code == 302
    with app.app_context():
        department = CompanyDepartment.query.filter_by(company_id=810, name=f"Root {parent_value or 'empty'}").one()
        assert department.parent_department_id is None


def test_department_cannot_set_parent_to_itself(client, app):
    with app.app_context():
        company = Company(id=801, name="Self Parent Co")
        department = CompanyDepartment(id=1801, company=company, name="Ban giám đốc")
        db.session.add_all([company, department])
        db.session.commit()

    login(client, "admin")
    response = client.post(
        "/partner-companies/801/departments/1801/edit",
        data={"name": "Ban giám đốc", "parent_department_id": "1801", "is_active": "on"},
    )
    assert response.status_code == 400
    assert "không thể là cấp trên của chính nó".encode() in response.data


def test_department_cannot_use_child_or_other_company_as_parent(client, app):
    with app.app_context():
        company = Company(id=811, name="Tree Co")
        other_company = Company(id=812, name="Other Tree Co")
        root = CompanyDepartment(id=1811, company=company, name="Root")
        child = CompanyDepartment(id=1812, company=company, name="Child", parent_department_id=1811)
        grandchild = CompanyDepartment(id=1813, company=company, name="Grandchild", parent_department_id=1812)
        other_department = CompanyDepartment(id=1814, company=other_company, name="Other Root")
        db.session.add_all([company, other_company, root, child, grandchild, other_department])
        db.session.commit()

    login(client, "admin")
    child_parent = client.post(
        "/partner-companies/811/departments/1811/edit",
        data={"name": "Root", "parent_department_id": "1813", "is_active": "on"},
    )
    assert child_parent.status_code == 400
    assert "Không thể chọn phòng ban con làm phòng ban cấp trên.".encode() in child_parent.data

    other_company_parent = client.post(
        "/partner-companies/811/departments/1811/edit",
        data={"name": "Root", "parent_department_id": "1814", "is_active": "on"},
    )
    assert other_company_parent.status_code == 400
    assert "Phòng ban cấp trên phải thuộc cùng công ty.".encode() in other_company_parent.data

    with app.app_context():
        root = db.session.get(CompanyDepartment, 1811)
        assert root.parent_department_id is None


def test_department_parent_form_excludes_current_department_and_descendants(client, app):
    with app.app_context():
        company = Company(id=813, name="Parent Options Co")
        root = CompanyDepartment(id=1815, company=company, name="Root")
        child = CompanyDepartment(id=1816, company=company, name="Child", parent_department_id=1815)
        grandchild = CompanyDepartment(id=1817, company=company, name="Grandchild", parent_department_id=1816)
        db.session.add_all([company, root, child, grandchild])
        db.session.commit()

    login(client, "admin")
    response = client.get("/partner-companies/813/departments/1815/edit")

    assert response.status_code == 200
    assert b'value="1815"' not in response.data
    assert b'value="1816"' not in response.data
    assert b'value="1817"' not in response.data
    assert b'<option value="">Kh\xc3\xb4ng c\xc3\xb3</option>' in response.data


def test_partner_form_uses_department_select_not_free_text(client, app):
    with app.app_context():
        company_id, department_id = create_company_department(company_id=802, company_name="Select Dept Co", department_name="Kỹ thuật")

    login(client, "admin")
    response = client.get("/partners/new")

    assert response.status_code == 200
    assert b'name="department_id"' in response.data
    assert b'name="department"' not in response.data
    assert str(department_id).encode() in response.data
    assert "Công ty này chưa có phòng ban".encode() in response.data


def test_partner_detail_shows_empty_company_note_text(client, app):
    with app.app_context():
        company = Company(id=101, name="Empty Note Co")
        db.session.add(company)
        db.session.commit()

    login(client, "super")
    response = client.get("/partner-companies/101")

    assert response.status_code == 200
    assert "Chưa có ghi chú.".encode() in response.data


def test_partner_birth_date_displays_dd_mm_yyyy(client, app):
    with app.app_context():
        partner = Partner(id=100, full_name="Date Person", birth_date=__import__("datetime").date(1990, 5, 24))
        db.session.add(partner)
        db.session.commit()

    login(client, "super")
    response = client.get("/partners/100")

    assert response.status_code == 200
    assert "24-05-1990".encode() in response.data


def test_partner_create_accepts_dd_mm_yyyy(client, app):
    with app.app_context():
        company_id, department_id = create_company_department()
    login(client, "admin")
    response = client.post(
        "/partners/new",
        data={"full_name": "Ngày Sinh", "company_id": str(company_id), "department_id": str(department_id), "position": "Giám đốc", "birth_date": "24-05-1990"},
    )

    assert response.status_code == 302
    with app.app_context():
        partner = Partner.query.filter_by(full_name="Ngày Sinh").one()
        assert partner.birth_date.isoformat() == "1990-05-24"


def test_partner_create_form_contains_birth_date_picker(client):
    login(client, "admin")
    response = client.get("/partners/new")

    assert response.status_code == 200
    assert b'name="birth_date"' in response.data
    assert b"js-date-picker" in response.data
    assert b"data-date-picker" in response.data


def test_partner_edit_form_displays_birth_date_dd_mm_yyyy(client, app):
    with app.app_context():
        partner = Partner(id=120, full_name="Edit Date", birth_date=__import__("datetime").date(1991, 6, 25))
        db.session.add(partner)
        db.session.commit()

    login(client, "admin")
    response = client.get("/partners/120/edit")

    assert response.status_code == 200
    assert b'value="25-06-1991"' in response.data


def test_invalid_birth_date_shows_vietnamese_error_and_preserves_form(client):
    login(client, "admin")
    response = client.post(
        "/partners/new",
        data={"full_name": "Sai Ngày", "birth_date": "1990/05/24", "position": "Giám đốc"},
    )

    assert response.status_code == 400
    assert "Ngày sinh phải có định dạng DD-MM-YYYY.".encode() in response.data
    assert "Sai Ngày".encode() in response.data
    assert "Giám đốc".encode() in response.data


def test_dynamic_date_field_renders_picker_accepts_and_rejects_dates(client, app):
    with app.app_context():
        date_field_id = create_field("Ngày sinh nhật", "birthday_note", "date", "Cá nhân")
        company_id, department_id = create_company_department()

    login(client, "admin")
    form = client.post(
        "/partners/new",
        data={
            "full_name": "",
            "fields[0][field_definition_id]": str(date_field_id),
            "fields[0][value]": "31-12-2026",
        },
    )
    assert b"js-date-picker" in form.data
    assert b"31-12-2026" in form.data

    invalid = client.post(
        "/partners/new",
        data={
            "full_name": "Ngày động lỗi",
            "company_id": str(company_id),
            "department_id": str(department_id),
            "position": "Giám đốc",
            "fields[0][field_definition_id]": str(date_field_id),
            "fields[0][value]": "2026/12/31",
        },
    )
    assert invalid.status_code == 400
    assert "Ngày không hợp lệ, vui lòng nhập theo định dạng DD-MM-YYYY.".encode() in invalid.data
    assert b"2026/12/31" in invalid.data

    created = client.post(
        "/partners/new",
        data={
            "full_name": "Ngày động",
            "company_id": str(company_id),
            "department_id": str(department_id),
            "position": "Giám đốc",
            "fields[0][field_definition_id]": str(date_field_id),
            "fields[0][value]": "31-12-2026",
        },
    )
    assert created.status_code == 302
    with app.app_context():
        partner = Partner.query.filter_by(full_name="Ngày động").one()
        assert partner.field_values[0].value_date.isoformat() == "2026-12-31"


def test_new_partner_form_does_not_render_all_dynamic_inputs_by_default(client, app):
    with app.app_context():
        create_field()
        create_field("Phong cách làm việc", "working_style", "select", "Phong cách")

    login(client, "admin")
    response = client.get("/partners/new")

    assert response.status_code == 200
    assert "Thêm trường dữ liệu".encode() in response.data
    assert "Trường tùy chỉnh".encode() not in response.data
    assert b'name="fields[0][field_definition_id]"' not in response.data


def test_submitting_selected_dynamic_field_saves_only_that_field(client, app):
    with app.app_context():
        hobby_id = create_field()
        create_field("Phong cách làm việc", "working_style", "select", "Phong cách")
        company_id, department_id = create_company_department()

    login(client, "admin")
    response = client.post(
        "/partners/new",
        data={
            "full_name": "Một Field",
            "company_id": str(company_id),
            "department_id": str(department_id),
            "position": "Giám đốc",
            "fields[0][field_definition_id]": str(hobby_id),
            "fields[0][value]": "Golf",
        },
    )

    assert response.status_code == 302
    with app.app_context():
        partner = Partner.query.filter_by(full_name="Một Field").one()
        assert len(partner.field_values) == 1
        assert partner.field_values[0].field_key_snapshot == "hobby"


def test_edit_partner_shows_existing_selected_field_and_can_remove_it(client, app):
    with app.app_context():
        field_id = create_field()
        field = db.session.get(PartnerFieldDefinition, field_id)
        company_id, department_id = create_company_department()
        partner = Partner(id=100, full_name="Có Field", company_id=company_id, department_id=department_id, position="Giám đốc")
        db.session.add(partner)
        db.session.flush()
        value = PartnerFieldValue(
                partner_id=partner.id,
                field_definition_id=field_id,
                field_label_snapshot=field.label,
                field_key_snapshot=field.field_key,
                field_type_snapshot=field.field_type,
                group_name_snapshot=field.group_name,
                value_text="Golf",
        )
        _add_with_sqlite_id(value)
        db.session.commit()

    login(client, "admin")
    edit = client.get("/partners/100/edit")
    assert "Golf".encode() in edit.data

    response = client.post("/partners/100/edit", data={"full_name": "Có Field", "company_id": str(company_id), "department_id": str(department_id), "position": "Giám đốc"})
    assert response.status_code == 302
    detail = client.get("/partners/100")
    assert "Golf".encode() not in detail.data


def test_create_edit_deactivate_field_collection(client, app):
    with app.app_context():
        first_id = create_field()
        second_id = create_field("Ngày sinh nhật", "birthday_note", "date", "Cá nhân")

    login(client, "admin")
    created = client.post(
        "/partner-field-collections/new",
        data={
            "name": "Hồ sơ cá nhân",
            "description": "Thông tin cá nhân",
            "field_definition_ids": [str(first_id), str(second_id)],
            "is_active": "on",
        },
    )
    assert created.status_code == 302

    form = client.get("/partners/new")
    assert "Hồ sơ cá nhân".encode() in form.data

    edited = client.post(
        "/partner-field-collections/1/edit",
        data={"name": "Hồ sơ cá nhân mới", "field_definition_ids": [str(first_id)], "is_active": "on"},
    )
    assert edited.status_code == 302
    deactivated = client.post("/partner-field-collections/1/deactivate")
    assert deactivated.status_code == 302
    hidden_form = client.get("/partners/new")
    assert "Hồ sơ cá nhân mới".encode() not in hidden_form.data

    with app.app_context():
        collection = PartnerFieldCollection.query.one()
        assert collection.name == "Hồ sơ cá nhân mới"
        assert collection.is_active is False


def test_collection_deduplicates_selected_fields(client, app):
    with app.app_context():
        field_id = create_field()

    login(client, "admin")
    response = client.post(
        "/partner-field-collections/new",
        data={"name": "Không trùng", "field_definition_ids": [str(field_id), str(field_id)], "is_active": "on"},
    )

    assert response.status_code == 302
    with app.app_context():
        collection = PartnerFieldCollection.query.one()
        assert len(collection.items) == 1


def test_relation_management_page_loads_and_sets_parent(client, app):
    with app.app_context():
        company = Company(id=200, name="Relation Co")
        director = CompanyDepartment(id=1200, company=company, name="Ban giám đốc")
        tech = CompanyDepartment(id=1201, company=company, name="Kỹ thuật", parent_department=director)
        manager = Partner(id=201, full_name="Manager A", company=company, department_id=1200, position="Giám đốc")
        staff = Partner(id=202, full_name="Staff B", company=company, department_id=1201, position="Kỹ sư")
        db.session.add_all([company, director, tech, manager, staff])
        db.session.commit()

    login(client, "admin")
    page = client.get("/partner-relations/company/200/manage")
    assert page.status_code == 200

    saved = client.post(
        "/partner-relations/company/200/manage",
        data={
            "partner_id": "202",
            "parent_partner_id": "201",
            "relationship_type": "manager",
        },
    )
    assert saved.status_code == 302

    detail = client.get("/partner-companies/200")
    assert "Manager A".encode() in detail.data
    assert "Staff B".encode() in detail.data
    assert "quản lý".encode() in detail.data
    with app.app_context():
        assert PartnerRelationship.query.filter_by(from_partner_id=201, to_partner_id=202).one()


def test_org_chart_renders_department_hierarchy_and_modal_summary(client, app):
    with app.app_context():
        company = Company(id=230, name="Multi Role Co")
        board = CompanyDepartment(id=1229, company=company, name="Ban lãnh đạo", is_special_department=True)
        director = CompanyDepartment(id=1230, company=company, name="Ban giám đốc", parent_department=board)
        tech = CompanyDepartment(id=1231, company=company, name="Phòng Kỹ thuật", parent_department=director)
        board_member = Partner(id=233, full_name="CFO", company=company, department_id=1229, position="CFO")
        ceo = Partner(id=231, full_name="CEO", company=company, department_id=1230, position="Tổng giám đốc")
        partner = Partner(id=232, full_name="Nguyễn Văn A", company=company, department_id=1231, position="Trưởng phòng", is_department_head=True)
        db.session.add_all([company, board, director, tech, board_member, ceo, partner])
        db.session.commit()

    login(client, "admin")
    first = client.post(
        "/partner-relations/company/230/manage",
        data={
            "partner_id": "232",
            "parent_partner_id": "231",
            "relationship_type": "manager",
        },
    )
    second = client.post(
        "/partner-relations/company/230/manage",
        data={
            "partner_id": "232",
            "parent_partner_id": "231",
            "relationship_type": "advisor",
        },
    )

    assert first.status_code == 302
    assert second.status_code == 302
    tree = client.get("/partner-relations/company/230/tree")
    assert tree.status_code == 200
    assert "Ban lãnh đạo".encode() in tree.data
    assert "Ban giám đốc".encode() in tree.data
    assert "Phòng Kỹ thuật".encode() in tree.data
    assert "CFO".encode() in tree.data
    assert tree.data.count("Nguyễn Văn A".encode()) == 1
    assert "Trưởng phòng:".encode() in tree.data
    assert b"partner-position-badge" in tree.data
    assert "Báo cáo cho: CEO".encode() not in tree.data
    assert b'data-tree-scroll' in tree.data
    assert b"data-department-node" in tree.data
    assert b"departmentSummaryModal" in tree.data

    summary = client.get("/partner-relations/departments/1231/summary")
    assert summary.status_code == 200
    assert "Nguyễn Văn A".encode() in summary.data
    assert "Báo cáo cho: CEO".encode() in summary.data
    assert b"/partners/232" in summary.data


def test_special_department_shows_all_members_on_chart(client, app):
    with app.app_context():
        company = Company(id=260, name="Special Co")
        leadership = CompanyDepartment(id=1260, company=company, name="Ban lãnh đạo", is_special_department=True)
        ceo = Partner(id=261, full_name="Nguyễn CEO", company=company, department_id=1260, position="CEO")
        cfo = Partner(id=262, full_name="Trần CFO", company=company, department_id=1260, position="CFO")
        db.session.add_all([company, leadership, ceo, cfo])
        db.session.commit()

    login(client, "admin")
    tree = client.get("/partner-relations/company/260/tree")

    assert tree.status_code == 200
    assert "Ban lãnh đạo".encode() in tree.data
    assert "Nguyễn CEO".encode() in tree.data
    assert "Trần CFO".encode() in tree.data
    assert "Phòng ban đặc biệt".encode() in tree.data


def test_relationship_form_auto_displays_partner_department_position_and_no_head_checkbox(client, app):
    with app.app_context():
        company = Company(id=270, name="Relation Display Co")
        department = CompanyDepartment(id=1270, company=company, name="Ban lãnh đạo", is_special_department=True)
        partner = Partner(id=271, full_name="Lê Quốc Cường", company=company, department_id=1270, position="COO")
        db.session.add_all([company, department, partner])
        db.session.commit()

    login(client, "admin")
    response = client.get("/partner-relations/company/270/manage")

    assert response.status_code == 200
    assert b'data-relation-partner-select' in response.data
    assert b'data-department="Ban l\xc3\xa3nh \xc4\x91\xe1\xba\xa1o"' in response.data
    assert b'data-position="COO"' in response.data
    assert b'data-relation-department-display' in response.data
    assert b'data-relation-position-display' in response.data
    assert "Là trưởng phòng ban?".encode() not in response.data
    assert "Không có".encode() in response.data


def test_partner_head_checkbox_rules_for_normal_and_special_departments(client, app):
    with app.app_context():
        company = Company(id=280, name="Head Rule Co")
        normal = CompanyDepartment(id=1280, company=company, name="Kỹ thuật")
        special = CompanyDepartment(id=1281, company=company, name="Ban lãnh đạo", is_special_department=True)
        db.session.add_all([company, normal, special])
        db.session.commit()

    login(client, "admin")
    form = client.get("/partners/new")
    assert form.status_code == 200
    assert "Là trưởng phòng".encode() in form.data
    assert b"data-is-special=\"1\"" in form.data

    normal_response = client.post(
        "/partners/new",
        data={"full_name": "Head Person", "company_id": "280", "department_id": "1280", "is_department_head": "on"},
    )
    assert normal_response.status_code == 302
    with app.app_context():
        head = Partner.query.filter_by(full_name="Head Person").one()
        assert head.is_department_head is True
        assert head.position == "Trưởng phòng"

    special_response = client.post(
        "/partners/new",
        data={
            "full_name": "Special Person",
            "company_id": "280",
            "department_id": "1281",
            "position": "COO",
            "is_department_head": "on",
        },
    )
    assert special_response.status_code == 302
    with app.app_context():
        special_partner = Partner.query.filter_by(full_name="Special Person").one()
        assert special_partner.is_department_head is False
        assert special_partner.position == "COO"


def test_none_relationship_type_does_not_render_reporting_line(client, app):
    with app.app_context():
        company = Company(id=290, name="None Relation Co")
        department = CompanyDepartment(id=1290, company=company, name="Ban lãnh đạo", is_special_department=True)
        partner = Partner(id=291, full_name="No Report", company=company, department_id=1290, position="CFO")
        parent = Partner(id=292, full_name="Parent Person", company=company, department_id=1290, position="CEO")
        db.session.add_all([company, department, partner, parent])
        db.session.commit()

    login(client, "admin")
    response = client.post(
        "/partner-relations/company/290/manage",
        data={"partner_id": "291", "parent_partner_id": "292", "relationship_type": "none"},
    )
    assert response.status_code == 302
    with app.app_context():
        relationship = PartnerRelationship.query.filter_by(partner_id=291).one()
        assert relationship.relationship_type == "none"
        assert relationship.parent_partner_id is None

    summary = client.get("/partner-relations/departments/1290/summary")
    assert summary.status_code == 200
    assert "Không có".encode() in summary.data
    assert "Báo cáo cho".encode() not in summary.data


def test_relationship_delete_uses_post(client, app):
    with app.app_context():
        company = Company(id=240, name="Delete Relation Co")
        department = CompanyDepartment(id=1240, company=company, name="Kỹ thuật")
        partner = Partner(id=241, full_name="Delete Person", company=company, department_id=1240, position="Kỹ sư")
        relationship = PartnerRelationship(
            id=242,
            company_id=240,
            department_id=1240,
            partner_id=241,
            from_partner_id=241,
            to_partner_id=241,
            department="Kỹ thuật",
            position_title="Kỹ sư",
            relationship_type="direct_report",
            is_active=True,
        )
        db.session.add_all([company, department, partner, relationship])
        db.session.commit()

    login(client, "admin")
    get_response = client.get("/partner-relations/company/240/relationships/242/delete")
    assert get_response.status_code == 405
    post_response = client.post("/partner-relations/company/240/relationships/242/delete")
    assert post_response.status_code == 302
    with app.app_context():
        assert db.session.get(PartnerRelationship, 242).is_active is False


def test_relationship_actions_are_mobile_accessible(client, app):
    with app.app_context():
        company = Company(id=250, name="Mobile Relation Co")
        department = CompanyDepartment(id=1250, company=company, name="Kỹ thuật")
        partner = Partner(id=251, full_name="Mobile Person", company=company, department_id=1250, position="Kỹ sư")
        relationship = PartnerRelationship(
            id=252,
            company_id=250,
            department_id=1250,
            partner_id=251,
            from_partner_id=251,
            to_partner_id=251,
            department="Kỹ thuật",
            position_title="Kỹ sư",
            relationship_type="direct_report",
            is_active=True,
        )
        db.session.add_all([company, department, partner, relationship])
        db.session.commit()

    login(client, "admin")
    response = client.get("/partner-relations/company/250/manage")

    assert response.status_code == 200
    assert 'aria-label="Xem"'.encode() in response.data
    assert 'aria-label="Sửa"'.encode() in response.data
    assert 'aria-label="Lưu trữ"'.encode() in response.data
    assert b"action-label" in response.data


def test_relation_cannot_set_self_or_cycle(client, app):
    with app.app_context():
        company = Company(id=210, name="Cycle Co")
        department = CompanyDepartment(id=1210, company=company, name="Ban điều hành")
        first = Partner(id=211, full_name="First", company=company, department_id=1210, position="Giám đốc")
        second = Partner(id=212, full_name="Second", company=company, department_id=1210, position="Phó giám đốc")
        db.session.add_all([company, department, first, second])
        db.session.commit()

    login(client, "admin")
    self_response = client.post(
        "/partner-relations/company/210/manage",
        data={
            "partner_id": "211",
            "parent_partner_id": "211",
            "relationship_type": "manager",
        },
    )
    assert self_response.status_code == 400
    assert "Đối tác không thể báo cáo cho chính mình.".encode() in self_response.data

    assert client.post(
        "/partner-relations/company/210/manage",
        data={
            "partner_id": "211",
            "parent_partner_id": "212",
            "relationship_type": "manager",
        },
    ).status_code == 302
    cycle_response = client.post(
        "/partner-relations/company/210/manage",
        data={
            "partner_id": "212",
            "parent_partner_id": "211",
            "relationship_type": "manager",
        },
    )
    assert cycle_response.status_code == 400
    assert "quan hệ vòng lặp".encode() in cycle_response.data


def test_partner_company_field_and_relation_filters_work(client, app):
    with app.app_context():
        company = Company(id=300, name="Filter Co", industry="MEP", phone="123", email="filter@example.com")
        other_company = Company(id=301, name="Other Co", industry="Xây dựng")
        partner = Partner(id=302, full_name="Filter Person", company=company, department="Kỹ thuật", position="Lead")
        db.session.add_all([company, other_company, partner])
        create_field("Filter Field", "filter_field", "number", "Filter Group")
        db.session.commit()

    login(client, "admin")
    partner_search = client.get("/partners/?q=Filter+Person")
    assert "Filter Person".encode() in partner_search.data

    partner_company = client.get("/partners/?company_id=300")
    assert "Filter Person".encode() in partner_company.data

    company_search = client.get("/partner-companies/?q=Filter")
    assert "Filter Co".encode() in company_search.data
    assert "Other Co".encode() not in company_search.data

    field_filter = client.get("/partner-fields/?field_type=number")
    assert "Filter Field".encode() in field_filter.data

    relation_filter = client.get("/partner-relations/?company_id=300")
    assert relation_filter.status_code == 302
    assert relation_filter.headers["Location"].endswith("/partner-relations/company/300?q=&department=")
