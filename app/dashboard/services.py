from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from zoneinfo import ZoneInfo

from flask_login import current_user
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.models import (
    DailyReport,
    DailyReportStatus,
    DailyReportSection,
    IssueSeverity,
    IssueStatus,
    PersistentIssue,
    Project,
    ProjectContractor,
    ProjectStatus,
    ProjectContractorAssignment,
    ProjectContractorAssignmentStatus,
    ProjectUpdate,
    SectionStatus,
)
from app.extensions import db
from app.ui import ASSIGNMENT_STATUS_LABELS, CONTRACTOR_ROLE_LABELS
RECENT_DASHBOARD_LIMIT = 5
SECTION_STATUS_LABELS = {
    "INFO": "Thông tin",
    "GOOD": "Tốt",
    "PROCESSING": "Đang xử lý",
    "ATTENTION": "Cần chú ý",
    "CRITICAL": "Khẩn cấp",
}
ISSUE_STATUS_LABELS = {
    "OPEN": "Mở",
    "PROCESSING": "Đang xử lý",
    "RESOLVED": "Đã xử lý",
    "CLOSED": "Đã đóng",
}
ISSUE_SEVERITY_LABELS = {
    "LOW": "Thấp",
    "MEDIUM": "Trung bình",
    "HIGH": "Cao",
    "CRITICAL": "Khẩn cấp",
}


class DashboardScopeType(str, Enum):
    SYSTEM = "SYSTEM"
    CUSTOMER = "CUSTOMER"
    PROJECT = "PROJECT"
    CONTRACTOR = "CONTRACTOR"


@dataclass(frozen=True)
class DashboardScope:
    """A non-persistent aggregation scope intersected with project access.

    Routes are responsible for action permissions.  This value object only
    provides the shared, data-level intersection so aggregates cannot expand
    beyond a user's effective project scope.
    """

    kind: DashboardScopeType
    customer_id: int | None = None
    project_id: int | None = None
    contractor_id: int | None = None

    @classmethod
    def system(cls):
        return cls(DashboardScopeType.SYSTEM)

    @classmethod
    def customer(cls, customer_id):
        return cls(DashboardScopeType.CUSTOMER, customer_id=int(customer_id))

    @classmethod
    def contractor(cls, contractor_id):
        return cls(DashboardScopeType.CONTRACTOR, contractor_id=int(contractor_id))

    def projects_query(self):
        query = Project.query.options(joinedload(Project.customer)).filter(Project.deleted_at.is_(None))
        if self.kind == DashboardScopeType.CUSTOMER:
            query = query.filter(Project.customer_id == self.customer_id)
        elif self.kind == DashboardScopeType.PROJECT:
            query = query.filter(Project.id == self.project_id)

        from app.project_memberships import accessible_project_ids

        project_ids = accessible_project_ids(current_user, ("can_view_project",))
        if project_ids is not None:
            query = query.filter(Project.id.in_(project_ids or [0]))
        return query


class DashboardFilterError(ValueError):
    pass


def project_dashboard_context(project):
    """Project Dashboard data is intentionally independent of retired legacy aggregates."""
    reports = DailyReport.query.filter(DailyReport.project_id == project.id).order_by(
        DailyReport.report_date.desc(),
        DailyReport.id.desc(),
    )
    report_history = reports.limit(RECENT_DASHBOARD_LIMIT).all()
    report_history_total = reports.order_by(None).count()
    # Keep aggregation independent from the report-history ordering. PostgreSQL
    # rejects an ORDER BY report_date on this GROUP BY overall_status query.
    rows = (
        db.session.query(DailyReport.overall_status, func.count(DailyReport.id))
        .filter(DailyReport.project_id == project.id)
        .group_by(DailyReport.overall_status)
        .order_by(DailyReport.overall_status)
        .all()
    )
    status_counts = {status: int(count) for status, count in rows}
    from app.project_memberships import user_has_project_capability
    can_view_issues = user_has_project_capability(current_user, project.id, "can_view_issues")
    open_issues = (
        PersistentIssue.query.filter(
            PersistentIssue.project_id == project.id,
            PersistentIssue.deleted_at.is_(None),
            PersistentIssue.status.in_([IssueStatus.OPEN.value, IssueStatus.PROCESSING.value]),
        ).order_by(PersistentIssue.severity.desc(), PersistentIssue.opened_date.desc(), PersistentIssue.id.desc()).limit(RECENT_DASHBOARD_LIMIT).all()
        if can_view_issues else []
    )
    recent_updates_query = ProjectUpdate.query.options(
        joinedload(ProjectUpdate.contractor_assignment).joinedload(ProjectContractorAssignment.contractor),
        joinedload(ProjectUpdate.created_by),
    ).filter(
        ProjectUpdate.project_id == project.id,
        ProjectUpdate.deleted_at.is_(None),
    ).order_by(ProjectUpdate.update_date.desc(), ProjectUpdate.created_at.desc(), ProjectUpdate.id.desc())
    recent_updates = recent_updates_query.limit(RECENT_DASHBOARD_LIMIT).all()
    return {
        "project": project,
        "report_history": report_history,
        "report_history_total": report_history_total,
        "report_dates": [report.report_date for report in report_history],
        "project_dashboard": project_dashboard_metrics(project),
        "can_view_issues": can_view_issues,
        "open_issues": open_issues,
        "recent_updates": recent_updates,
        "recent_updates_total": recent_updates_query.order_by(None).count(),
        "cards": {
            "total_reports": sum(status_counts.values()),
            "good_reports": status_counts.get(DailyReportStatus.GOOD.value, 0),
            "processing_reports": status_counts.get(DailyReportStatus.PROCESSING.value, 0),
            "attention_reports": status_counts.get(DailyReportStatus.ATTENTION.value, 0),
            "critical_reports": status_counts.get(DailyReportStatus.CRITICAL.value, 0),
        },
    }


def project_dashboard_metrics(project, selected_date=None, days=7):
    """Project-only aggregates; section statuses remain their native five values."""
    selected_date = selected_date or datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
    statuses = [item.value for item in SectionStatus]
    rows = db.session.query(DailyReportSection.status, func.count(DailyReportSection.id)).join(
        DailyReport, DailyReport.id == DailyReportSection.daily_report_id
    ).filter(DailyReport.project_id == project.id, DailyReport.report_date == selected_date).group_by(DailyReportSection.status).all()
    pie = {status: 0 for status in statuses}; pie.update(dict(rows))
    start = selected_date - timedelta(days=days - 1)
    trend_rows = db.session.query(DailyReport.report_date, DailyReportSection.status, func.count(DailyReportSection.id)).join(
        DailyReportSection, DailyReportSection.daily_report_id == DailyReport.id
    ).filter(DailyReport.project_id == project.id, DailyReport.report_date.between(start, selected_date)).group_by(DailyReport.report_date, DailyReportSection.status).order_by(DailyReport.report_date).all()
    labels = [(start + timedelta(days=offset)).isoformat() for offset in range(days)]
    datasets = {status: [0] * len(labels) for status in statuses}; positions = {label: index for index, label in enumerate(labels)}
    for report_date, status, count in trend_rows: datasets[status][positions[report_date.isoformat()]] = count
    assignments = ProjectContractorAssignment.query.filter(
        ProjectContractorAssignment.project_id == project.id,
        ProjectContractorAssignment.status == ProjectContractorAssignmentStatus.ACTIVE.value,
    )
    issue_counts = dict(db.session.query(PersistentIssue.status, func.count(PersistentIssue.id)).filter(
        PersistentIssue.project_id == project.id, PersistentIssue.deleted_at.is_(None)
    ).group_by(PersistentIssue.status).all())
    return {"selected_date": selected_date, "section_pie": pie, "section_trend": {"labels": labels, "datasets": datasets},
            "submitted_today": DailyReport.query.filter_by(project_id=project.id, report_date=selected_date).count() > 0,
            "construction_active": assignments.filter_by(role="CONSTRUCTION").count(), "solution_active": assignments.filter_by(role="SOLUTION").count(),
            "issue_counts": issue_counts, "latest_update": ProjectUpdate.query.filter(ProjectUpdate.project_id == project.id, ProjectUpdate.deleted_at.is_(None)).order_by(ProjectUpdate.update_date.desc(), ProjectUpdate.id.desc()).first()}


def project_section_status_payload(project, selected_date=None):
    metrics = project_dashboard_metrics(project, selected_date=selected_date)
    keys = [item.value for item in SectionStatus]
    labels = ["Thông tin", "Tốt", "Đang xử lý", "Cần chú ý", "Khẩn cấp"]
    values = [int(metrics["section_pie"][key]) for key in keys]
    latest = metrics["latest_update"]
    report = DailyReport.query.filter_by(project_id=project.id, report_date=metrics["selected_date"]).first()
    return {"selected_date": metrics["selected_date"].isoformat(), "timezone": "Asia/Ho_Chi_Minh",
            "submission": {"submitted": report is not None, "report_id": report.id if report else None, "report_date": report.report_date.isoformat() if report else None},
            "section_status": {"labels": labels, "keys": keys, "values": values, "total": sum(values)},
            "trend": {"days": metrics["section_trend"]["labels"], "series": {key: [int(value) for value in metrics["section_trend"]["datasets"][key]] for key in keys}},
            "contractors": {"construction_active": metrics["construction_active"], "solution_active": metrics["solution_active"]},
            "persistent_issues": {"total": sum(metrics["issue_counts"].values()), "by_status": metrics["issue_counts"]},
            "latest_project_update": {"id": latest.id, "date": latest.update_date.isoformat(), "title": latest.title} if latest else None}


def dashboard_scope_context(scope, selected_date=None, days=7):
    """Build Customer/System dashboard data from aggregate SQL queries.

    The expected-report denominator is explicitly the active projects in the
    effective scope.  Paused, completed, archived, and soft-deleted projects
    are deliberately not counted as missing for the selected date.
    """
    selected_date = selected_date or datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
    effective_projects = scope.projects_query()
    active_projects = effective_projects.filter(Project.status == ProjectStatus.ACTIVE.value).order_by(Project.code).all()
    active_project_ids = [project.id for project in active_projects]
    all_project_ids = [project_id for (project_id,) in effective_projects.with_entities(Project.id).all()]

    submitted_rows = []
    if active_project_ids:
        submitted_rows = (
            db.session.query(DailyReport.project_id, DailyReport.id, DailyReport.overall_status)
            .filter(
                DailyReport.project_id.in_(active_project_ids),
                DailyReport.report_date == selected_date,
            )
            .all()
        )
    reports_by_project = {project_id: {"id": report_id, "status": status} for project_id, report_id, status in submitted_rows}
    project_rows = [
        {
            "project": project,
            "report": reports_by_project.get(project.id),
            "submitted": project.id in reports_by_project,
        }
        for project in active_projects
    ]
    recent_project_rows = [
        {"project": project, "report": reports_by_project.get(project.id), "submitted": project.id in reports_by_project}
        for project in effective_projects.filter(Project.status == ProjectStatus.ACTIVE.value).order_by(Project.code).limit(RECENT_DASHBOARD_LIMIT).all()
    ]
    missing_projects = [row["project"] for row in project_rows if not row["submitted"]]

    section_pie = _section_status_counts(active_project_ids, selected_date)
    section_trend = _section_status_trend(active_project_ids, selected_date, days)
    issue_counts = _issue_dashboard_counts(all_project_ids)
    contractor_counts = _active_contractor_counts(all_project_ids)
    updates = _recent_project_updates(all_project_ids)
    recent_updates_total = ProjectUpdate.query.filter(ProjectUpdate.project_id.in_(all_project_ids or [0]), ProjectUpdate.deleted_at.is_(None)).count()

    expected_count = len(active_project_ids)
    submitted_count = len(reports_by_project)
    customer_count = 0
    if all_project_ids:
        customer_count = (
            db.session.query(func.count(func.distinct(Project.customer_id)))
            .filter(Project.id.in_(all_project_ids), Project.customer_id.is_not(None))
            .scalar()
            or 0
        )

    return {
        "scope": scope,
        "selected_date": selected_date,
        "timezone": "Asia/Ho_Chi_Minh",
        "projects": project_rows,
        "recent_projects": recent_project_rows,
        "active_projects_total": len(active_project_ids),
        "missing_projects": missing_projects,
        "recent_updates": updates,
        "recent_updates_total": recent_updates_total,
        "section_pie": section_pie,
        "section_trend": section_trend,
        "issue_counts": issue_counts,
        "contractor_counts": contractor_counts,
        "cards": {
            "customers": int(customer_count),
            "active_projects": expected_count,
            "submitted_reports": submitted_count,
            "missing_reports": expected_count - submitted_count,
            "submission_rate": round((submitted_count / expected_count) * 100, 1) if expected_count else 0,
            "distinct_contractors": contractor_counts["distinct"],
            "persistent_issues": issue_counts["total"],
        },
    }


def dashboard_scope_payload(scope, selected_date=None, days=7):
    """CSP-safe chart contract shared by Customer and System dashboards."""
    context = dashboard_scope_context(scope, selected_date=selected_date, days=days)
    section_keys = [item.value for item in SectionStatus]
    issue_status_keys = [item.value for item in IssueStatus]
    severity_keys = [item.value for item in IssueSeverity]
    project_labels = [row["project"].code for row in context["projects"]]
    return {
        "selected_date": context["selected_date"].isoformat(),
        "timezone": context["timezone"],
        "section_status": {
            "keys": section_keys,
            "labels": [SECTION_STATUS_LABELS[key] for key in section_keys],
            "values": [int(context["section_pie"][key]) for key in section_keys],
        },
        "trend": {
            "days": context["section_trend"]["labels"],
            "series": {
                key: [int(value) for value in context["section_trend"]["datasets"][key]]
                for key in section_keys
            },
        },
        "submissions": {
            "labels": project_labels,
            "values": [1 if row["submitted"] else 0 for row in context["projects"]],
        },
        "overall_status": {
            "labels": project_labels,
            "keys": [row["report"]["status"] if row["report"] else None for row in context["projects"]],
        },
        "persistent_issues": {
            "status": {
                "keys": issue_status_keys,
                "labels": [ISSUE_STATUS_LABELS[key] for key in issue_status_keys],
                "values": [int(context["issue_counts"]["by_status"].get(key, 0)) for key in issue_status_keys],
            },
            "severity": {
                "keys": severity_keys,
                "labels": [ISSUE_SEVERITY_LABELS[key] for key in severity_keys],
                "values": [int(context["issue_counts"]["by_severity"].get(key, 0)) for key in severity_keys],
            },
            "by_project": {
                "labels": project_labels,
                "values": [int(context["issue_counts"]["by_project"].get(row["project"].id, 0)) for row in context["projects"]],
            },
        },
        "contractors": {
            "labels": ["Thi công", "Giải pháp"],
            "values": [
                int(context["contractor_counts"]["by_role"].get("CONSTRUCTION", 0)),
                int(context["contractor_counts"]["by_role"].get("SOLUTION", 0)),
            ],
        },
    }


CONTRACTOR_ASSIGNMENT_STATUSES = [item.value for item in ProjectContractorAssignmentStatus]
CONTRACTOR_STATUS_LABELS = ASSIGNMENT_STATUS_LABELS


def parse_contractor_dashboard_filters(args):
    """Parse non-persistent Contractor Dashboard filters.

    An omitted status intentionally keeps current and completed assignment
    history, while suppressing ended assignments.  END and ALL are explicit
    historical choices.
    """
    assignment_status = args.get("assignment_status", "").strip().upper()
    if assignment_status and assignment_status not in {*CONTRACTOR_ASSIGNMENT_STATUSES, "ALL"}:
        raise DashboardFilterError("Bộ lọc trạng thái liên kết không hợp lệ.")
    return {"project_id": args.get("project_id", type=int), "assignment_status": assignment_status}


def contractor_projects_query(contractor_id):
    """Visible projects which have ever had an assignment for contractor."""
    return (
        DashboardScope.contractor(contractor_id).projects_query()
        .join(ProjectContractorAssignment, ProjectContractorAssignment.project_id == Project.id)
        .filter(ProjectContractorAssignment.contractor_id == contractor_id)
        .distinct()
    )


def contractor_is_visible(contractor_id):
    """Global project scope may inspect an otherwise unassigned contractor."""
    from app.project_memberships import has_global_project_scope, is_project_admin, is_viewer_admin

    if is_project_admin(current_user) or is_viewer_admin(current_user) or has_global_project_scope(current_user):
        return True
    return contractor_projects_query(contractor_id).with_entities(Project.id).first() is not None


def _contractor_assignments_query(contractor_id, filters):
    query = (
        ProjectContractorAssignment.query.options(
            joinedload(ProjectContractorAssignment.project).joinedload(Project.customer),
            joinedload(ProjectContractorAssignment.contractor),
        )
        .join(Project, Project.id == ProjectContractorAssignment.project_id)
        .filter(
            ProjectContractorAssignment.contractor_id == contractor_id,
            Project.deleted_at.is_(None),
        )
    )
    visible_projects = contractor_projects_query(contractor_id).with_entities(Project.id)
    query = query.filter(ProjectContractorAssignment.project_id.in_(visible_projects))
    if filters.get("project_id"):
        if not contractor_projects_query(contractor_id).filter(Project.id == filters["project_id"]).with_entities(Project.id).first():
            raise DashboardFilterError("Dự án không thuộc phạm vi đối tác này.")
        query = query.filter(ProjectContractorAssignment.project_id == filters["project_id"])
    status = filters.get("assignment_status", "")
    if not status:
        query = query.filter(ProjectContractorAssignment.status != ProjectContractorAssignmentStatus.ENDED.value)
    elif status != "ALL":
        query = query.filter(ProjectContractorAssignment.status == status)
    return query


def contractor_dashboard_context(contractor, filters):
    """Context for a contractor, limited to assignment-backed visible projects."""
    assignment_query = _contractor_assignments_query(contractor.id, filters)
    assignments_total = assignment_query.order_by(None).count()
    assignments = assignment_query.order_by(
        ProjectContractorAssignment.status != ProjectContractorAssignmentStatus.ENDED.value,
        ProjectContractorAssignment.started_on.desc(),
        ProjectContractorAssignment.id.desc(),
    ).limit(RECENT_DASHBOARD_LIMIT).all()

    active_assignment_query = _contractor_assignments_query(
        contractor.id, {"project_id": filters.get("project_id"), "assignment_status": "ACTIVE"}
    ).filter(Project.status == ProjectStatus.ACTIVE.value)
    active_project_ids = active_assignment_query.with_entities(ProjectContractorAssignment.project_id).distinct().subquery()
    active_projects = Project.query.options(joinedload(Project.customer)).filter(Project.id.in_(active_project_ids.select())).order_by(Project.code).all()
    customer_count = (
        db.session.query(func.count(func.distinct(Project.customer_id)))
        .filter(Project.id.in_(active_project_ids.select()), Project.customer_id.is_not(None))
        .scalar() or 0
    )
    active_role_rows = active_assignment_query.with_entities(
        ProjectContractorAssignment.role, func.count(ProjectContractorAssignment.id)
    ).group_by(ProjectContractorAssignment.role).all()
    active_role_counts = {role: 0 for role in CONTRACTOR_ROLE_LABELS}
    active_role_counts.update({role: int(count) for role, count in active_role_rows})

    role_rows = assignment_query.with_entities(
        ProjectContractorAssignment.role, func.count(ProjectContractorAssignment.id)
    ).group_by(ProjectContractorAssignment.role).all()
    status_rows = assignment_query.with_entities(
        ProjectContractorAssignment.status, func.count(ProjectContractorAssignment.id)
    ).group_by(ProjectContractorAssignment.status).all()
    role_counts = {role: 0 for role in CONTRACTOR_ROLE_LABELS}
    role_counts.update({role: int(count) for role, count in role_rows})
    status_counts = {status: 0 for status in CONTRACTOR_ASSIGNMENT_STATUSES}
    status_counts.update({status: int(count) for status, count in status_rows})

    assignment_ids = assignment_query.with_entities(ProjectContractorAssignment.id).subquery()
    project_ids = assignment_query.with_entities(ProjectContractorAssignment.project_id).distinct().subquery()
    latest_update = (
        ProjectUpdate.query.options(joinedload(ProjectUpdate.project))
        .filter(ProjectUpdate.contractor_assignment_id.in_(assignment_ids.select()), ProjectUpdate.deleted_at.is_(None))
        .order_by(ProjectUpdate.update_date.desc(), ProjectUpdate.created_at.desc(), ProjectUpdate.id.desc())
        .first()
    )
    updates_total = ProjectUpdate.query.filter(ProjectUpdate.contractor_assignment_id.in_(assignment_ids.select()), ProjectUpdate.deleted_at.is_(None)).count()
    updates = (
        ProjectUpdate.query.options(
            joinedload(ProjectUpdate.project),
            joinedload(ProjectUpdate.contractor_assignment).joinedload(ProjectContractorAssignment.contractor),
        )
        .filter(ProjectUpdate.contractor_assignment_id.in_(assignment_ids.select()), ProjectUpdate.deleted_at.is_(None))
        .order_by(ProjectUpdate.update_date.desc(), ProjectUpdate.created_at.desc(), ProjectUpdate.id.desc())
        .limit(RECENT_DASHBOARD_LIMIT).all()
    )

    latest_report_dates = (
        db.session.query(DailyReport.project_id, func.max(DailyReport.report_date).label("report_date"))
        .filter(DailyReport.project_id.in_(project_ids.select()))
        .group_by(DailyReport.project_id).subquery()
    )
    latest_reports = (
        DailyReport.query.options(joinedload(DailyReport.project))
        .join(latest_report_dates, (DailyReport.project_id == latest_report_dates.c.project_id) & (DailyReport.report_date == latest_report_dates.c.report_date))
        .order_by(DailyReport.report_date.desc(), DailyReport.id.desc()).limit(RECENT_DASHBOARD_LIMIT).all()
    )
    from app.project_memberships import has_any_project_capability
    can_view_issues = has_any_project_capability(current_user, ("can_view_issues",))
    issues = (
        PersistentIssue.query.options(joinedload(PersistentIssue.project))
        .filter(PersistentIssue.project_id.in_(project_ids.select()), PersistentIssue.deleted_at.is_(None))
        .order_by(PersistentIssue.opened_date.desc(), PersistentIssue.id.desc()).limit(RECENT_DASHBOARD_LIMIT).all()
        if can_view_issues else []
    )
    projects = contractor_projects_query(contractor.id).order_by(Project.code).all()
    return {
        "contractor": contractor,
        "filters": filters,
        "filter_projects": projects,
        "assignments": assignments,
        "assignments_total": assignments_total,
        "active_projects": active_projects,
        "updates": updates,
        "updates_total": updates_total,
        "latest_reports": latest_reports,
        "issues": issues,
        "can_view_issues": can_view_issues,
        "role_counts": role_counts,
        "status_counts": status_counts,
        "role_labels": CONTRACTOR_ROLE_LABELS,
        "status_labels": CONTRACTOR_STATUS_LABELS,
        "cards": {
            "active_projects": len(active_projects),
            "customers": int(customer_count),
            "construction": active_role_counts["CONSTRUCTION"],
            "solution": active_role_counts["SOLUTION"],
            "assignments": sum(status_counts.values()),
        },
        "latest_update": latest_update,
    }


def contractor_dashboard_payload(contractor, filters):
    context = contractor_dashboard_context(contractor, filters)
    projects_by_customer = {}
    for project in context["active_projects"]:
        key = project.customer.name if project.customer else "Chưa phân loại"
        projects_by_customer[key] = projects_by_customer.get(key, 0) + 1
    return {
        "contractor": {"id": contractor.id, "name": contractor.name, "short_name": contractor.short_name, "is_active": contractor.is_active},
        "filters": filters,
        "cards": context["cards"],
        "projects_by_customer": {"labels": list(projects_by_customer), "values": list(projects_by_customer.values())},
        "assignment_roles": {"labels": [CONTRACTOR_ROLE_LABELS[key] for key in CONTRACTOR_ROLE_LABELS], "keys": list(CONTRACTOR_ROLE_LABELS), "values": [context["role_counts"][key] for key in CONTRACTOR_ROLE_LABELS]},
        "assignment_statuses": {"labels": [CONTRACTOR_STATUS_LABELS[key] for key in CONTRACTOR_ASSIGNMENT_STATUSES], "keys": CONTRACTOR_ASSIGNMENT_STATUSES, "values": [context["status_counts"][key] for key in CONTRACTOR_ASSIGNMENT_STATUSES]},
        "latest_update": {"id": context["latest_update"].id, "title": context["latest_update"].title, "date": context["latest_update"].update_date.isoformat()} if context["latest_update"] else None,
    }


def _section_status_counts(project_ids, selected_date):
    counts = {item.value: 0 for item in SectionStatus}
    if not project_ids:
        return counts
    rows = (
        db.session.query(DailyReportSection.status, func.count(DailyReportSection.id))
        .join(DailyReport, DailyReport.id == DailyReportSection.daily_report_id)
        .filter(DailyReport.project_id.in_(project_ids), DailyReport.report_date == selected_date)
        .group_by(DailyReportSection.status)
        .all()
    )
    counts.update({status: int(count) for status, count in rows})
    return counts


def _section_status_trend(project_ids, selected_date, days):
    statuses = [item.value for item in SectionStatus]
    start = selected_date - timedelta(days=days - 1)
    labels = [(start + timedelta(days=offset)).isoformat() for offset in range(days)]
    datasets = {status: [0] * len(labels) for status in statuses}
    if not project_ids:
        return {"labels": labels, "datasets": datasets}
    rows = (
        db.session.query(DailyReport.report_date, DailyReportSection.status, func.count(DailyReportSection.id))
        .join(DailyReportSection, DailyReportSection.daily_report_id == DailyReport.id)
        .filter(
            DailyReport.project_id.in_(project_ids),
            DailyReport.report_date.between(start, selected_date),
        )
        .group_by(DailyReport.report_date, DailyReportSection.status)
        .order_by(DailyReport.report_date)
        .all()
    )
    positions = {label: index for index, label in enumerate(labels)}
    for report_date, status, count in rows:
        datasets[status][positions[report_date.isoformat()]] = int(count)
    return {"labels": labels, "datasets": datasets}


def _issue_dashboard_counts(project_ids):
    empty = {
        "total": 0,
        "by_status": {item.value: 0 for item in IssueStatus},
        "by_severity": {item.value: 0 for item in IssueSeverity},
        "by_project": {},
        "by_project_status": {},
        "by_project_severity": {},
    }
    if not project_ids:
        return empty
    base = PersistentIssue.query.filter(
        PersistentIssue.project_id.in_(project_ids),
        PersistentIssue.deleted_at.is_(None),
    )
    status_rows = base.with_entities(PersistentIssue.status, func.count(PersistentIssue.id)).group_by(PersistentIssue.status).all()
    severity_rows = base.with_entities(PersistentIssue.severity, func.count(PersistentIssue.id)).group_by(PersistentIssue.severity).all()
    project_rows = base.with_entities(PersistentIssue.project_id, func.count(PersistentIssue.id)).group_by(PersistentIssue.project_id).all()
    project_status_rows = base.with_entities(PersistentIssue.project_id, PersistentIssue.status, func.count(PersistentIssue.id)).group_by(PersistentIssue.project_id, PersistentIssue.status).all()
    project_severity_rows = base.with_entities(PersistentIssue.project_id, PersistentIssue.severity, func.count(PersistentIssue.id)).group_by(PersistentIssue.project_id, PersistentIssue.severity).all()
    empty["by_status"].update({status: int(count) for status, count in status_rows})
    empty["by_severity"].update({severity: int(count) for severity, count in severity_rows})
    empty["by_project"].update({project_id: int(count) for project_id, count in project_rows})
    for project_id, status, count in project_status_rows:
        empty["by_project_status"].setdefault(project_id, {})[status] = int(count)
    for project_id, severity, count in project_severity_rows:
        empty["by_project_severity"].setdefault(project_id, {})[severity] = int(count)
    empty["total"] = sum(empty["by_status"].values())
    return empty


def _active_contractor_counts(project_ids):
    result = {"distinct": 0, "by_role": {"CONSTRUCTION": 0, "SOLUTION": 0}}
    if not project_ids:
        return result
    base = ProjectContractorAssignment.query.filter(
        ProjectContractorAssignment.project_id.in_(project_ids),
        ProjectContractorAssignment.status == ProjectContractorAssignmentStatus.ACTIVE.value,
    )
    result["distinct"] = int(base.with_entities(func.count(func.distinct(ProjectContractorAssignment.contractor_id))).scalar() or 0)
    rows = base.with_entities(ProjectContractorAssignment.role, func.count(ProjectContractorAssignment.id)).group_by(ProjectContractorAssignment.role).all()
    result["by_role"].update({role: int(count) for role, count in rows})
    return result


def _recent_project_updates(project_ids):
    if not project_ids:
        return []
    return (
        ProjectUpdate.query.options(
            joinedload(ProjectUpdate.project),
            joinedload(ProjectUpdate.project).joinedload(Project.customer),
            joinedload(ProjectUpdate.contractor_assignment).joinedload(ProjectContractorAssignment.contractor),
            joinedload(ProjectUpdate.created_by),
        )
        .filter(ProjectUpdate.project_id.in_(project_ids), ProjectUpdate.deleted_at.is_(None))
        .order_by(ProjectUpdate.update_date.desc(), ProjectUpdate.created_at.desc(), ProjectUpdate.id.desc())
        .limit(RECENT_DASHBOARD_LIMIT)
        .all()
    )
