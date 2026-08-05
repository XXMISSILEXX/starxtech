from datetime import date

from app.extensions import db
from app.models import AuditLog, PersistentIssue, PersistentIssueSection, ProjectUser, ReportCategory


def login(client, username_or_email, password="password123"):
    return client.post("/login", data={"username_or_email": username_or_email, "password": password})


def seed_issue(app, statuses=("OPEN", "OPEN")):
    with app.app_context():
        issue = PersistentIssue(
            id=5101,
            project_id=1,
            title="Issue section actions",
            description="Mô tả tổng quan",
            severity="HIGH",
            status="OPEN",
            opened_date=date(2026, 8, 5),
            created_by_user_id=1,
        )
        db.session.add(issue)
        db.session.flush()
        sections = []
        for sort_order, (category_id, status) in enumerate(zip(range(1, len(statuses) + 1), statuses)):
            section = PersistentIssueSection(
                persistent_issue_id=issue.id,
                report_category_id=category_id,
                severity="HIGH",
                status=status,
                description=f"Mô tả {category_id}",
                proposed_solution=f"Giải pháp {category_id}",
                sort_order=sort_order,
                created_by_id=1,
            )
            db.session.add(section)
            sections.append(section)
        db.session.commit()
        return issue.id, [
            {
                "id": section.id,
                "category_id": section.report_category_id,
                "status": section.status,
                "description": section.description,
                "proposed_solution": section.proposed_solution,
            }
            for section in sections
        ]


def edit_payload(sections):
    payload = {
        "title": "Issue section actions",
        "description": "Mô tả tổng quan",
        "severity": "HIGH",
        "opened_date": "2026-08-05",
    }
    for index, section in enumerate(sections):
        prefix = f"sections-{index}-"
        payload.update(
            {
                f"{prefix}section-id": str(section.get("id", "")),
                f"{prefix}category_id": str(section["category_id"]),
                f"{prefix}severity": "HIGH",
                f"{prefix}status": section["status"],
                f"{prefix}due_date": "",
                f"{prefix}owner_user_id": "",
                f"{prefix}description": section["description"],
                f"{prefix}proposed_solution": section["proposed_solution"],
            }
        )
    return payload


def enable_reporter_issue_editing(app):
    with app.app_context():
        membership = ProjectUser.query.filter_by(project_id=1, user_id=3).one()
        membership.can_edit_issues = True
        db.session.commit()


def section_actions(section_id):
    return [
        row.action
        for row in AuditLog.query.filter_by(
            entity_type="PersistentIssueSection",
            entity_id=section_id,
        ).order_by(AuditLog.id).all()
    ]


def test_editor_without_close_capability_cannot_close_but_can_resolve_and_edit_sections(client, app):
    issue_id, sections = seed_issue(app)
    enable_reporter_issue_editing(app)
    login(client, "reporter")

    denied = [dict(section) for section in sections]
    denied[0]["status"] = "CLOSED"
    denied[1]["description"] = "Không được lưu"
    response = client.post(f"/reports/issues/{issue_id}/edit", data=edit_payload(denied))

    assert response.status_code == 400
    assert "Bạn không có quyền đóng hoặc mở lại hạng mục.".encode() in response.data
    with app.app_context():
        persisted = db.session.get(PersistentIssueSection, sections[0]["id"])
        untouched = db.session.get(PersistentIssueSection, sections[1]["id"])
        assert persisted.status == "OPEN"
        assert untouched.description == "Mô tả 2"
        assert section_actions(sections[0]["id"]) == []
        assert section_actions(sections[1]["id"]) == []

    resolved = [dict(section) for section in sections]
    resolved[0]["status"] = "RESOLVED"
    assert client.post(f"/reports/issues/{issue_id}/edit", data=edit_payload(resolved)).status_code == 302
    with app.app_context():
        assert db.session.get(PersistentIssueSection, sections[0]["id"]).status == "RESOLVED"
        assert section_actions(sections[0]["id"]) == ["issue.section.update"]

    edited = [dict(section) for section in resolved]
    edited[1]["description"] = "Mô tả đã sửa"
    edited[1]["proposed_solution"] = "Giải pháp đã sửa"
    assert client.post(f"/reports/issues/{issue_id}/edit", data=edit_payload(edited)).status_code == 302
    with app.app_context():
        updated = db.session.get(PersistentIssueSection, sections[1]["id"])
        assert (updated.description, updated.proposed_solution) == ("Mô tả đã sửa", "Giải pháp đã sửa")
        assert section_actions(sections[1]["id"]) == ["issue.section.update"]


def test_close_and_reopen_section_require_close_capability_and_emit_one_audit(client, app):
    issue_id, sections = seed_issue(app, statuses=("RESOLVED", "OPEN"))
    login(client, "pm")

    closed = [dict(section) for section in sections]
    closed[0]["status"] = "CLOSED"
    assert client.post(f"/reports/issues/{issue_id}/edit", data=edit_payload(closed)).status_code == 302
    with app.app_context():
        assert section_actions(sections[0]["id"]) == ["issue.section.close"]
        assert AuditLog.query.filter_by(action="issue.update", entity_id=issue_id).count() == 0

    client.post("/logout")
    enable_reporter_issue_editing(app)
    login(client, "reporter")
    reopened = [dict(section) for section in closed]
    reopened[0]["status"] = "OPEN"
    response = client.post(f"/reports/issues/{issue_id}/edit", data=edit_payload(reopened))

    assert response.status_code == 400
    assert "Bạn không có quyền đóng hoặc mở lại hạng mục.".encode() in response.data
    with app.app_context():
        assert db.session.get(PersistentIssueSection, sections[0]["id"]).status == "CLOSED"
        assert section_actions(sections[0]["id"]) == ["issue.section.close"]

    client.post("/logout")
    login(client, "pm")
    assert client.post(f"/reports/issues/{issue_id}/edit", data=edit_payload(reopened)).status_code == 302
    with app.app_context():
        assert section_actions(sections[0]["id"]) == ["issue.section.close", "issue.section.reopen"]


def test_section_delete_snapshot_is_complete_and_new_section_does_not_emit_audit(client, app):
    issue_id, sections = seed_issue(app)
    login(client, "super")

    assert client.post(f"/reports/issues/{issue_id}/edit", data=edit_payload([sections[1]])).status_code == 302
    with app.app_context():
        deleted = AuditLog.query.filter_by(action="issue.section.delete", entity_id=sections[0]["id"]).one()
        assert set(deleted.old_values_json) == {
            "report_category_id", "severity", "status", "due_date", "owner_user_id",
            "description", "proposed_solution", "created_at", "created_by_id",
        }
        assert deleted.old_values_json["description"] == "Mô tả 1"
        audit_count = AuditLog.query.count()
        db.session.add(ReportCategory(id=90, project_id=1, name="Hạng mục mới", sort_order=90, is_active=True))
        db.session.commit()

    created = [dict(sections[1])]
    created.append(
        {
            "id": "",
            "category_id": 90,
            "status": "OPEN",
            "description": "Hạng mục được tạo",
            "proposed_solution": "Giải pháp mới",
        }
    )
    assert client.post(f"/reports/issues/{issue_id}/edit", data=edit_payload(created)).status_code == 302
    with app.app_context():
        assert PersistentIssueSection.query.filter_by(persistent_issue_id=issue_id, report_category_id=90).count() == 1
        assert AuditLog.query.count() == audit_count


def test_closing_last_section_does_not_audit_derived_issue_rollup(client, app):
    issue_id, sections = seed_issue(app, statuses=("RESOLVED",))
    login(client, "pm")
    closed = [dict(sections[0])]
    closed[0]["status"] = "CLOSED"

    assert client.post(f"/reports/issues/{issue_id}/edit", data=edit_payload(closed)).status_code == 302
    with app.app_context():
        issue = db.session.get(PersistentIssue, issue_id)
        assert issue.status == "CLOSED"
        assert issue.closed_date is not None
        assert section_actions(sections[0]["id"]) == ["issue.section.close"]
        assert AuditLog.query.filter_by(entity_type="PersistentIssue", entity_id=issue_id).count() == 0


def test_legacy_issue_close_routes_and_list_actions_are_absent(client, app):
    login(client, "super")

    assert client.post("/reports/issues/1/close").status_code == 404
    assert client.post("/reports/issues/1/reopen").status_code == 404
    for url in ("/reports/issues", "/reports/projects/1/issues"):
        response = client.get(url)
        assert response.status_code == 200
        assert b"/close" not in response.data
        assert b"/reopen" not in response.data
