from app.extensions import db
from app.models import Company, CompanyDepartment, Partner, PartnerFieldDefinition, PartnerFieldValue, PartnerRelationship
from app.cli import COMPANY_DEMOS, FIELD_DEMOS, PARTNER_DEMOS, sync_partner_demo_sequences
from tests.test_auth_permissions import login


def run_seed(app):
    runner = app.test_cli_runner()
    return runner.invoke(args=["seed-partner-demo"])


def test_seed_partner_demo_command_exits_successfully(app):
    result = run_seed(app)

    assert result.exit_code == 0
    assert "Đã tạo dữ liệu mẫu Quản lý đối tác" in result.output
    assert "- Dữ liệu mở rộng:" in result.output


def test_seed_partner_demo_command_success(app):
    result = run_seed(app)

    assert result.exit_code == 0


def test_seed_partner_demo_creates_partner_values_with_partner_id(app):
    result = run_seed(app)

    assert result.exit_code == 0
    with app.app_context():
        values = PartnerFieldValue.query.all()
        assert values
        assert all(value.partner_id is not None for value in values)


def test_seed_partner_demo_creates_sample_companies_fields_and_partners(app):
    result = run_seed(app)

    assert result.exit_code == 0
    with app.app_context():
        assert Company.query.filter(Company.name.in_([item["name"] for item in COMPANY_DEMOS])).count() == 5
        assert (
            PartnerFieldDefinition.query.filter(
                PartnerFieldDefinition.field_key.in_([item["field_key"] for item in FIELD_DEMOS])
            ).count()
            == 8
        )
        assert Partner.query.filter(Partner.email.in_([item["email"] for item in PARTNER_DEMOS])).count() == len(PARTNER_DEMOS)
        assert CompanyDepartment.query.filter_by(name="Ban giám đốc").count() >= 3
        assert PartnerRelationship.query.count() == len(PARTNER_DEMOS)


def test_seed_partner_demo_is_idempotent(app):
    first = run_seed(app)
    with app.app_context():
        first_field_value_count = PartnerFieldValue.query.count()
    second = run_seed(app)

    assert first.exit_code == 0
    assert second.exit_code == 0
    with app.app_context():
        assert Company.query.filter(Company.name.in_([item["name"] for item in COMPANY_DEMOS])).count() == 5
        assert (
            PartnerFieldDefinition.query.filter(
                PartnerFieldDefinition.field_key.in_([item["field_key"] for item in FIELD_DEMOS])
            ).count()
            == 8
        )
        assert Partner.query.filter(Partner.email.in_([item["email"] for item in PARTNER_DEMOS])).count() == len(PARTNER_DEMOS)
        assert PartnerFieldValue.query.count() == first_field_value_count
        assert PartnerRelationship.query.count() == len(PARTNER_DEMOS)
    assert "- Công ty: 0 tạo mới, 5 bỏ qua" in second.output
    assert "- Trường dữ liệu: 0 tạo mới, 8 bỏ qua" in second.output
    assert f"- Đối tác: 0 tạo mới, {len(PARTNER_DEMOS)} bỏ qua" in second.output
    assert "- Dữ liệu mở rộng: 0 tạo mới," in second.output
    assert f"- Quan hệ: 0 tạo mới, {len(PARTNER_DEMOS)} bỏ qua" in second.output


def test_seed_partner_demo_idempotent(app):
    assert run_seed(app).exit_code == 0
    with app.app_context():
        company_count = Company.query.filter(Company.name.in_([item["name"] for item in COMPANY_DEMOS])).count()
        field_count = (
            PartnerFieldDefinition.query.filter(
                PartnerFieldDefinition.field_key.in_([item["field_key"] for item in FIELD_DEMOS])
            ).count()
        )
        partner_count = Partner.query.filter(Partner.email.in_([item["email"] for item in PARTNER_DEMOS])).count()
        value_count = PartnerFieldValue.query.count()

    assert run_seed(app).exit_code == 0
    with app.app_context():
        assert Company.query.filter(Company.name.in_([item["name"] for item in COMPANY_DEMOS])).count() == company_count
        assert (
            PartnerFieldDefinition.query.filter(
                PartnerFieldDefinition.field_key.in_([item["field_key"] for item in FIELD_DEMOS])
            ).count()
            == field_count
        )
        assert Partner.query.filter(Partner.email.in_([item["email"] for item in PARTNER_DEMOS])).count() == partner_count
        assert PartnerFieldValue.query.count() == value_count


def test_seed_partner_demo_after_partial_existing_data(app):
    with app.app_context():
        db.session.add(
            Company(
                id=100,
                name="Công ty Xây dựng An Bình",
                industry="Dữ liệu có sẵn",
                email="old-anbinh@example.com",
            )
        )
        db.session.add(
            PartnerFieldDefinition(
                id=100,
                label="Sở thích cũ",
                field_key="hobby",
                field_type="text",
                group_name="Cũ",
                is_active=True,
            )
        )
        db.session.commit()

    result = run_seed(app)

    assert result.exit_code == 0
    with app.app_context():
        assert Company.query.filter_by(name="Công ty Xây dựng An Bình").count() == 1
        assert PartnerFieldDefinition.query.filter_by(field_key="hobby").count() == 1
        assert Partner.query.filter_by(email="minh.nguyen@anbinh.example.com").one()
        assert PartnerFieldValue.query.filter(PartnerFieldValue.partner_id.is_(None)).count() == 0


def test_seed_partner_demo_after_partial_existing_departments(app):
    with app.app_context():
        company = Company(id=200, name="Công ty Cơ điện Minh Phát")
        department = CompanyDepartment(id=200, company=company, name="Ban giám đốc")
        db.session.add_all([company, department])
        db.session.commit()

    result = run_seed(app)

    assert result.exit_code == 0
    with app.app_context():
        company = Company.query.filter_by(name="Công ty Cơ điện Minh Phát").one()
        assert CompanyDepartment.query.filter_by(company_id=company.id, name="Ban giám đốc").count() == 1
        assert CompanyDepartment.query.filter_by(company_id=company.id, name="Kỹ thuật").count() == 1


def test_seed_partner_demo_sequence_sync_helper_is_safe_on_sqlite(app):
    with app.app_context():
        sync_partner_demo_sequences()


def test_partner_pages_show_demo_data_after_seed(client, app):
    assert run_seed(app).exit_code == 0
    login(client, "super")

    dashboard = client.get("/partners/dashboard")
    partners = client.get("/partners/")
    companies = client.get("/partner-companies/")
    fields = client.get("/partner-fields/")

    assert dashboard.status_code == 200
    assert "Tổng đối tác".encode() in dashboard.data
    assert f">{len(PARTNER_DEMOS)}<".encode() in dashboard.data
    assert partners.status_code == 200
    assert "Nguyễn Văn Minh".encode() in partners.data
    assert "Lê Hoàng Anh".encode() in partners.data
    assert companies.status_code == 200
    assert "Công ty Xây dựng An Bình".encode() in companies.data
    assert fields.status_code == 200
    assert "Sở thích".encode() in fields.data
    assert "working_style".encode() in fields.data


def test_company_detail_shows_demo_partners_and_relationship_tree(client, app):
    assert run_seed(app).exit_code == 0
    login(client, "super")

    with app.app_context():
        company = Company.query.filter_by(name="Công ty Xây dựng An Bình").one()

    response = client.get(f"/partner-companies/{company.id}")

    assert response.status_code == 200
    assert "Nguyễn Văn Minh".encode() in response.data
    assert "Trần Thị Lan".encode() in response.data
    assert "Sơ đồ quan hệ".encode() in response.data
    assert "quản lý".encode() in response.data


def test_seed_partner_demo_creates_departments_and_hierarchy(client, app):
    assert run_seed(app).exit_code == 0
    login(client, "super")

    with app.app_context():
        company = Company.query.filter_by(name="Công ty Cơ điện Minh Phát").one()
        ban_giam_doc = CompanyDepartment.query.filter_by(company_id=company.id, name="Ban giám đốc").one()
        ky_thuat = CompanyDepartment.query.filter_by(company_id=company.id, name="Kỹ thuật").one()
        qaqc = CompanyDepartment.query.filter_by(company_id=company.id, name="QA/QC").one()
        assert ky_thuat.parent_department_id == ban_giam_doc.id
        assert qaqc.parent_department_id == ky_thuat.id

    tree = client.get(f"/partner-relations/company/{company.id}/tree")
    assert tree.status_code == 200
    assert "Ban giám đốc".encode() in tree.data
    assert "Kỹ thuật".encode() in tree.data
    assert "QA/QC".encode() in tree.data
    assert "Trưởng phòng".encode() in tree.data

    summary = client.get(f"/partner-relations/departments/{qaqc.id}/summary")
    assert summary.status_code == 200
    assert "Báo cáo cho".encode() in summary.data


def test_seed_partner_demo_creates_special_departments(client, app):
    assert run_seed(app).exit_code == 0
    login(client, "super")

    with app.app_context():
        company = Company.query.filter_by(name="Ban Quản lý Dự án StarX").one()
        leadership = CompanyDepartment.query.filter_by(company_id=company.id, name="Ban lãnh đạo").one()
        board = CompanyDepartment.query.filter_by(company_id=company.id, name="Hội đồng quản trị").one()
        assert leadership.is_special_department is True
        assert board.is_special_department is True
        assert leadership.parent_department_id == board.id
        assert Partner.query.filter_by(department_id=leadership.id, is_department_head=True).count() == 0
        assert PartnerRelationship.query.filter_by(company_id=company.id, relationship_type="none").count() >= 1

    tree = client.get(f"/partner-relations/company/{company.id}/tree")
    assert tree.status_code == 200
    assert "Ban lãnh đạo".encode() in tree.data
    assert "Trần Thị Bích".encode() in tree.data
    assert "CFO".encode() in tree.data
    assert "Phòng ban đặc biệt".encode() in tree.data


def test_seed_partner_demo_sets_normal_department_heads_on_partners(app):
    assert run_seed(app).exit_code == 0
    with app.app_context():
        hanh = Partner.query.filter_by(email="hanh.nguyen@starx.example.com").one()
        dung = Partner.query.filter_by(email="dung.ta@starx.example.com").one()
        assert hanh.is_department_head is True
        assert hanh.position == "Trưởng phòng"
        assert dung.is_department_head is True
        assert dung.position == "Trưởng phòng"


def test_seed_partner_demo_companies_have_expected_ban_giam_doc(app):
    assert run_seed(app).exit_code == 0
    expected = [
        "Ban Quản lý Dự án StarX",
        "Công ty Cơ điện Minh Phát",
        "Công ty Tư vấn Thiết kế Nova",
        "Công ty Vật liệu Hòa Sơn",
    ]
    with app.app_context():
        for company_name in expected:
            company = Company.query.filter_by(name=company_name).one()
            assert CompanyDepartment.query.filter_by(company_id=company.id, name="Ban giám đốc").count() == 1


def test_dynamic_field_values_appear_on_partner_detail(client, app):
    assert run_seed(app).exit_code == 0
    login(client, "super")

    with app.app_context():
        partner = Partner.query.filter_by(email="minh.nguyen@anbinh.example.com").one()

    response = client.get(f"/partners/{partner.id}")

    assert response.status_code == 200
    assert "Sở thích".encode() in response.data
    assert "Golf, cà phê sáng".encode() in response.data
    assert "Mức độ thân thiết".encode() in response.data
    assert "4".encode() in response.data


def test_partner_detail_shows_dynamic_demo_values(client, app):
    assert run_seed(app).exit_code == 0
    login(client, "super")

    with app.app_context():
        partner = Partner.query.filter_by(email="minh.nguyen@anbinh.example.com").one()

    response = client.get(f"/partners/{partner.id}")

    assert response.status_code == 200
    assert "Golf, cà phê sáng".encode() in response.data


def test_seeded_field_snapshots_survive_definition_label_change(client, app):
    assert run_seed(app).exit_code == 0
    with app.app_context():
        field = PartnerFieldDefinition.query.filter_by(field_key="hobby").one()
        field.label = "Sở thích đã đổi"
        db.session.commit()
        partner = Partner.query.filter_by(email="minh.nguyen@anbinh.example.com").one()

    login(client, "super")
    response = client.get(f"/partners/{partner.id}")

    assert response.status_code == 200
    assert "Sở thích".encode() in response.data
    assert "Golf, cà phê sáng".encode() in response.data
    assert "Sở thích đã đổi".encode() not in response.data
