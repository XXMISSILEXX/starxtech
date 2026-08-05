from datetime import date

from app.extensions import db
from app.models import PersistentIssue, PersistentIssueSection, ReportCategory


def login(client, username_or_email, password="password123"):
    return client.post("/login", data={"username_or_email": username_or_email, "password": password})


def issue_payload(title="Vấn đề có hạng mục", sections=()):
    data = {
        "title": title,
        "project_id": "1",
        "description": "Mô tả tổng quan.",
        "severity": "LOW",
        "opened_date": "2026-08-05",
    }
    for index, section in enumerate(sections):
        prefix = f"sections-{index}-"
        data.update(
            {
                f"{prefix}section-id": section.get("id", ""),
                f"{prefix}category_id": str(section["category_id"]),
                f"{prefix}severity": section.get("severity", "MEDIUM"),
                f"{prefix}status": section.get("status", "OPEN"),
                f"{prefix}due_date": section.get("due_date", ""),
                f"{prefix}owner_user_id": section.get("owner_user_id", ""),
                f"{prefix}description": section.get("description", "Mô tả hạng mục."),
                f"{prefix}proposed_solution": section.get("proposed_solution", "Giải pháp."),
            }
        )
    return data


def live_sections(issue_id):
    return PersistentIssueSection.query.filter(
        PersistentIssueSection.persistent_issue_id == issue_id,
        PersistentIssueSection.deleted_at.is_(None),
    ).order_by(PersistentIssueSection.sort_order, PersistentIssueSection.id).all()


def test_global_create_saves_two_sections_and_rollup(client, app):
    login(client, "super")
    response = client.post(
        "/reports/issues/new",
        data=issue_payload(
            sections=(
                {"category_id": 1, "severity": "CRITICAL", "status": "PROCESSING", "due_date": "2026-08-10", "owner_user_id": "3"},
                {"category_id": 2, "status": "CLOSED", "due_date": "2026-08-01"},
            ),
        ),
    )
    assert response.status_code == 302
    with app.app_context():
        issue = PersistentIssue.query.filter_by(title="Vấn đề có hạng mục").one()
        sections = live_sections(issue.id)
        assert [(section.report_category_id, section.sort_order) for section in sections] == [(1, 0), (2, 1)]
        assert (issue.status, issue.due_date, issue.severity) == ("PROCESSING", date(2026, 8, 10), "LOW")
        assert sections[0].created_by_id == 1


def test_project_create_saves_two_sections_and_rollup(client, app):
    login(client, "super")
    response = client.post(
        "/reports/projects/1/issues/create",
        data=issue_payload(
            title="Tạo theo dự án",
            sections=(
                {"category_id": 1, "status": "OPEN", "due_date": "2026-08-12"},
                {"category_id": 2, "status": "CLOSED"},
            ),
        ),
    )
    assert response.status_code == 302
    with app.app_context():
        issue = PersistentIssue.query.filter_by(title="Tạo theo dự án").one()
        assert len(live_sections(issue.id)) == 2
        assert (issue.status, issue.due_date) == ("OPEN", date(2026, 8, 12))


def test_create_without_sections_is_allowed_and_open(client, app):
    login(client, "super")
    response = client.post("/reports/issues/new", data=issue_payload(title="Không có hạng mục"))
    assert response.status_code == 302
    with app.app_context():
        issue = PersistentIssue.query.filter_by(title="Không có hạng mục").one()
        assert (issue.status, issue.due_date) == ("OPEN", None)


def test_duplicate_categories_are_rejected_without_creating_rows(client, app):
    login(client, "super")
    with app.app_context():
        before_issues, before_sections = PersistentIssue.query.count(), PersistentIssueSection.query.count()
    response = client.post(
        "/reports/issues/new",
        data=issue_payload(sections=({"category_id": 1}, {"category_id": 1, "status": "PROCESSING"})),
    )
    assert response.status_code == 400
    assert "Hạng mục không được trùng trong cùng vấn đề.".encode() in response.data
    with app.app_context():
        assert (PersistentIssue.query.count(), PersistentIssueSection.query.count()) == (before_issues, before_sections)


def test_editing_and_removing_sections_recalculates_rollup(client, app):
    login(client, "super")
    client.post(
        "/reports/issues/new",
        data=issue_payload(
            title="Sửa hạng mục",
            sections=({"category_id": 1, "status": "OPEN", "due_date": "2026-08-10"}, {"category_id": 2, "status": "CLOSED"}),
        ),
    )
    with app.app_context():
        issue = PersistentIssue.query.filter_by(title="Sửa hạng mục").one()
        first, second = live_sections(issue.id)
        issue_id, first_id, second_id = issue.id, first.id, second.id
    response = client.post(
        f"/reports/issues/{issue_id}/edit",
        data=issue_payload(
            title="Sửa hạng mục",
            sections=({"id": first_id, "category_id": 1, "status": "CLOSED"}, {"id": second_id, "category_id": 2, "status": "CLOSED"}),
        ),
    )
    assert response.status_code == 302
    with app.app_context():
        updated_sections = live_sections(issue_id)
        assert db.session.get(PersistentIssue, issue_id).status == "CLOSED"
        assert all(section.updated_by_id == 1 for section in updated_sections)
    response = client.post(f"/reports/issues/{issue_id}/edit", data=issue_payload(title="Sửa hạng mục"))
    assert response.status_code == 302
    with app.app_context():
        issue = db.session.get(PersistentIssue, issue_id)
        assert issue.status == "OPEN"
        assert not live_sections(issue_id)
        assert db.session.get(PersistentIssueSection, first_id).deleted_at is not None


def test_section_sort_order_is_assigned_from_form_order(client, app):
    with app.app_context():
        db.session.add(ReportCategory(id=4, project_id=1, name="An toàn", sort_order=3, is_active=True))
        db.session.commit()
    login(client, "super")
    response = client.post(
        "/reports/issues/new",
        data=issue_payload(title="Ba hạng mục", sections=({"category_id": 2}, {"category_id": 1}, {"category_id": 4})),
    )
    assert response.status_code == 302
    with app.app_context():
        issue = PersistentIssue.query.filter_by(title="Ba hạng mục").one()
        assert [(section.report_category_id, section.sort_order) for section in live_sections(issue.id)] == [(2, 0), (1, 1), (4, 2)]


def test_edit_form_keeps_disabled_existing_category_and_hides_used_choices(client, app):
    with app.app_context():
        issue = PersistentIssue(id=3101, project_id=1, title="Danh mục tắt", severity="LOW", status="OPEN", opened_date=date(2026, 8, 5), created_by_user_id=1)
        db.session.add(issue)
        db.session.flush()
        db.session.add_all(
            [
                PersistentIssueSection(persistent_issue_id=issue.id, report_category_id=1, severity="LOW", status="OPEN", created_by_id=1),
                PersistentIssueSection(persistent_issue_id=issue.id, report_category_id=2, severity="LOW", status="OPEN", created_by_id=1),
            ]
        )
        db.session.get(ReportCategory, 1).is_active = False
        db.session.commit()
    login(client, "super")
    response = client.get("/reports/issues/3101/edit")
    assert response.status_code == 200
    assert b'option value="1" selected' in response.data
    assert response.data.count(b'<option value="1"') == 1


def test_issue_form_has_no_overview_status_due_date_or_owner_fields(client):
    login(client, "super")
    for url in ("/reports/issues/new?project_id=1", "/reports/projects/1/issues/create"):
        response = client.get(url)
        assert response.status_code == 200
        assert b'name="status"' not in response.data
        assert b'name="due_date"' not in response.data
        assert b'name="owner_user_id"' not in response.data
        assert response.data.index(b'data-issue-sections') < response.data.index(b'persistent-issue-sections.js')


def test_unauthorized_create_does_not_create_issue_or_sections(client, app):
    login(client, "reporter")
    with app.app_context():
        before_issues, before_sections = PersistentIssue.query.count(), PersistentIssueSection.query.count()
    response = client.post("/reports/issues/new", data={**issue_payload(sections=({"category_id": 1},)), "project_id": "1"})
    assert response.status_code == 403
    with app.app_context():
        assert (PersistentIssue.query.count(), PersistentIssueSection.query.count()) == (before_issues, before_sections)
