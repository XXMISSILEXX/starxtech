from datetime import date, timedelta

import pytest

from app.extensions import db
from app.models import AuditLog, DailyReport, PersistentIssue, Project, ProjectContractor, ProjectContractorAssignment, ProjectUpdate
from app.project_operations.services import create_project_update, end_assignment, soft_delete_project_update, updates_query


def _assignment(app, project_id=1, name="VTS", role="SOLUTION", status="ACTIVE"):
    with app.app_context():
        contractor = ProjectContractor(name=name, normalized_name=name.casefold())
        db.session.add(contractor); db.session.flush()
        assignment = ProjectContractorAssignment(project_id=project_id, contractor_id=contractor.id, role=role, status=status)
        db.session.add(assignment); db.session.commit()
        return assignment.id


def test_general_and_assignment_update_are_scoped_and_ordered(app):
    assignment_id = _assignment(app)
    with app.app_context():
        project = db.session.get(Project, 1); assignment = db.session.get(ProjectContractorAssignment, assignment_id)
        general = create_project_update(project=project, update_type="GENERAL", title="Chung", content="Tiến độ chung", update_date=date.today() - timedelta(days=1), actor_id=1)
        handover = create_project_update(project=project, assignment=assignment, update_type="HANDOVER", title="Đã bàn giao xong 2 hạng mục", content="VTS hoàn tất", update_date=date.today(), actor_id=1)
        db.session.commit()
        assert [item.id for item in updates_query(project_id=1).all()] == [handover.id, general.id]
        assert [item.id for item in updates_query(assignment_id=assignment_id).all()] == [handover.id]
        assert handover.contractor_assignment.project_id == 1


def test_cross_project_and_ended_assignment_are_rejected_without_side_effects(app):
    assignment_id = _assignment(app, project_id=2)
    with app.app_context():
        before = ProjectUpdate.query.count(); project = db.session.get(Project, 1); assignment = db.session.get(ProjectContractorAssignment, assignment_id)
        with pytest.raises(ValueError, match="không thuộc"):
            create_project_update(project=project, assignment=assignment, update_type="HANDOVER", title="Blocked", content="Blocked", update_date=date.today(), actor_id=1)
        end_assignment(assignment); db.session.commit()
        with pytest.raises(ValueError, match="đã kết thúc"):
            create_project_update(project=db.session.get(Project, 2), assignment=assignment, update_type="HANDOVER", title="Blocked", content="Blocked", update_date=date.today(), actor_id=1)
        assert ProjectUpdate.query.count() == before


def test_soft_delete_hides_timeline_and_keeps_audit_without_report_issue_side_effects(app):
    with app.app_context():
        project = db.session.get(Project, 1)
        update = create_project_update(project=project, update_type="NOTE", title="Lưu ý", content="Nội dung", update_date=date.today(), actor_id=1)
        db.session.commit(); report_count, issue_count = DailyReport.query.count(), PersistentIssue.query.count()
        soft_delete_project_update(update, actor_id=1); db.session.commit()
        assert updates_query(project_id=1).count() == 0
        assert ProjectUpdate.query.filter_by(id=update.id).one().deleted_at is not None
        assert AuditLog.query.filter_by(action="project_update.delete", entity_id=update.id).count() == 1
        assert (DailyReport.query.count(), PersistentIssue.query.count()) == (report_count, issue_count)
