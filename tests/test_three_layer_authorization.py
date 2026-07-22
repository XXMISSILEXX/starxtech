from app.extensions import db
from app.models import ProjectUser, Role, User
from app.project_memberships import preset_flags, user_has_project_capability


def test_membership_flags_are_project_scope_source_of_truth(app):
    with app.app_context():
        reporter = User.query.filter_by(username="reporter").one()
        assert user_has_project_capability(reporter, 1, "can_create_reports")
        assert not user_has_project_capability(reporter, 2, "can_create_reports")
        assert not user_has_project_capability(reporter, 1, "can_upload_documents")


def test_mixed_membership_capabilities_do_not_depend_on_global_role(app):
    with app.app_context():
        role = Role(code="MEDIA_ONLY", name="Media only", is_system=False)
        db.session.add(role); db.session.flush()
        user = User(id=7, full_name="Mixed", username="mixed", password_hash="x", legacy_role="MEDIA_ONLY", role=role)
        db.session.add(user); db.session.flush()
        membership = ProjectUser(id=3, project_id=1, user_id=user.id, project_role_code="PROJECT_REPORTER", **preset_flags("PROJECT_REPORTER"))
        membership.can_upload_documents = True
        db.session.add(membership); db.session.commit()
        assert user_has_project_capability(user, 1, "can_create_reports")
        assert user_has_project_capability(user, 1, "can_upload_documents")
        assert not user_has_project_capability(user, 2, "can_view_project")
