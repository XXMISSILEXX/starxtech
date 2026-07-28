"""Secure regression for ISSUE-002: editing an issue must not authorize deletion."""

from datetime import date

pytest_plugins = ("tests.conftest",)

from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import Permission, PersistentIssue, ProjectUser, Role, RolePermission, User


def _login(client, username):
    # The shared TestConfig disables CSRF, which is the repository's normal test convention.
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def test_issue_editor_without_issues_delete_cannot_soft_delete_issue(client, app):
    with app.app_context():
        role = Role(id=9105, code="AUDIT_ISSUE_EDITOR", name="Audit issue editor", is_system=False)
        actor = User(
            id=9105,
            full_name="Audit Issue Editor",
            username="audit-issue-editor",
            email="audit-issue-editor@example.com",
            password_hash=generate_password_hash("password123"),
            role=role,
            legacy_role=role.code,
        )
        db.session.add_all([role, actor])
        db.session.flush()
        module_permission = Permission.query.filter_by(code="modules.reports.access").one()
        db.session.add(RolePermission(role_id=role.id, permission_id=module_permission.id))
        db.session.add(ProjectUser(
            id=9105,
            project_id=1,
            user_id=actor.id,
            project_role_code="CUSTOM",
            is_active=True,
            can_edit_issues=True,
        ))
        issue = PersistentIssue(
            id=9105,
            project_id=1,
            title="Audit destructive issue",
            description="Only an editor is assigned.",
            severity="HIGH",
            status="OPEN",
            opened_date=date(2026, 7, 28),
            created_by_user_id=1,
        )
        db.session.add(issue)
        db.session.commit()
        issue_id = issue.id

    assert _login(client, "audit-issue-editor").status_code == 302
    response = client.post(f"/reports/issues/{issue_id}/delete")

    with app.app_context():
        db.session.expire_all()
        persisted_issue = db.session.get(PersistentIssue, issue_id)
        issue_remains_active = persisted_issue is not None and persisted_issue.deleted_at is None

    secure = response.status_code in {400, 403, 404, 422} and issue_remains_active
    assert secure, (
        "secure behavior must require the dedicated issues.delete permission and retain the issue; "
        f"got HTTP {response.status_code}, issue remains active={issue_remains_active}"
    )
