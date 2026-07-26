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
    ProjectStatus,
    ProjectUser,
    User,
    ProjectContractorAssignment,
    ProjectContractorAssignmentStatus,
    ProjectUpdate,
    SectionStatus,
)
from app.extensions import db
from app.reports.services import accessible_projects_query


OPEN_ISSUE_STATUSES = [IssueStatus.OPEN.value, IssueStatus.PROCESSING.value]
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

    @classmethod
    def system(cls):
        return cls(DashboardScopeType.SYSTEM)

    @classmethod
    def customer(cls, customer_id):
        return cls(DashboardScopeType.CUSTOMER, customer_id=int(customer_id))

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


def parse_filters(args):
    filters = {
        "project_id": args.get("project_id", type=int),
        "from_date": _parse_date(args.get("from_date", "").strip(), "from_date"),
        "to_date": _parse_date(args.get("to_date", "").strip(), "to_date"),
        "overall_status": args.get("overall_status", "").strip(),
        "reporter": args.get("reporter", type=int),
    }
    if filters["overall_status"] and filters["overall_status"] not in [
        status.value for status in DailyReportStatus
    ]:
        raise DashboardFilterError("Bộ lọc trạng thái báo cáo không hợp lệ.")
    return filters


def dashboard_context(filters):
    reports = filtered_reports_query(filters)
    # A report dashboard may be visible without the separately granted issue
    # resource.  Do not leak issue counters or rows in that case.
    from app.project_memberships import has_any_project_capability
    issues = filtered_issues_query(filters) if has_any_project_capability(current_user, ("can_view_issues",)) else None
    open_issues = issues.filter(PersistentIssue.status.in_(OPEN_ISSUE_STATUSES)) if issues is not None else None
    critical_issues = issues.filter(PersistentIssue.severity == "CRITICAL") if issues is not None else None
    status_counts = _status_counts(reports)

    return {
        "can_view_issues": issues is not None,
        "filters": filters,
        "projects": accessible_projects_query().all(),
        "reporters": accessible_reporters(),
        "statuses": [status.value for status in DailyReportStatus],
        "cards": {
            "total_reports": reports.count(),
            "good_reports": status_counts.get(DailyReportStatus.GOOD.value, 0),
            "processing_reports": status_counts.get(DailyReportStatus.PROCESSING.value, 0),
            "attention_reports": status_counts.get(DailyReportStatus.ATTENTION.value, 0),
            "critical_reports": status_counts.get(DailyReportStatus.CRITICAL.value, 0),
            "total_issues": issues.count() if issues is not None else 0,
            "open_issues": open_issues.count() if open_issues is not None else 0,
            "critical_issues": critical_issues.count() if critical_issues is not None else 0,
        },
        "latest_reports": reports.order_by(
            DailyReport.report_date.desc(),
            DailyReport.id.desc(),
        )
        .limit(10)
        .all(),
        "open_issues": open_issues.order_by(
            PersistentIssue.severity.desc(),
            PersistentIssue.opened_date.desc(),
            PersistentIssue.id.desc(),
        )
        .limit(10)
        .all() if open_issues is not None else [],
        "recent_issues": issues.order_by(
            PersistentIssue.opened_date.desc(),
            PersistentIssue.id.desc(),
        )
        .limit(10)
        .all() if issues is not None else [],
    }


def project_dashboard_context(project):
    filters = {"project_id": project.id, "from_date": None, "to_date": None, "overall_status": "", "reporter": None}
    context = dashboard_context(filters)
    reports = filtered_reports_query(filters).order_by(
        DailyReport.report_date.desc(),
        DailyReport.id.desc(),
    )
    context.update(
        {
            "project": project,
            "report_history": reports.limit(30).all(),
            "report_dates": [report.report_date for report in reports.limit(30).all()],
            "project_dashboard": project_dashboard_metrics(project),
        }
    )
    return context


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
    missing_projects = [row["project"] for row in project_rows if not row["submitted"]]

    section_pie = _section_status_counts(active_project_ids, selected_date)
    section_trend = _section_status_trend(active_project_ids, selected_date, days)
    issue_counts = _issue_dashboard_counts(all_project_ids)
    contractor_counts = _active_contractor_counts(all_project_ids)
    updates = _recent_project_updates(all_project_ids)

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
        "missing_projects": missing_projects,
        "recent_updates": updates,
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
            joinedload(ProjectUpdate.contractor_assignment).joinedload(ProjectContractorAssignment.contractor),
        )
        .filter(ProjectUpdate.project_id.in_(project_ids), ProjectUpdate.deleted_at.is_(None))
        .order_by(ProjectUpdate.update_date.desc(), ProjectUpdate.created_at.desc(), ProjectUpdate.id.desc())
        .limit(10)
        .all()
    )


def status_chart_data(filters):
    from app.ui import REPORT_STATUS_LABELS
    counts = _status_counts(filtered_reports_query(filters))
    statuses = [status.value for status in DailyReportStatus]
    return {"labels": [REPORT_STATUS_LABELS[status] for status in statuses], "counts": [counts.get(status, 0) for status in statuses]}


def report_count_chart_data(filters):
    query = filtered_reports_query(filters)
    group_format = "%Y-%m"
    if filters.get("from_date") and filters.get("to_date"):
        days = (filters["to_date"] - filters["from_date"]).days
        if days <= 62:
            group_format = "%Y-%m-%d"

    if group_format == "%Y-%m-%d" and _is_sqlite():
        label_expr = func.strftime("%Y-%m-%d", DailyReport.report_date)
    elif group_format == "%Y-%m-%d":
        label_expr = func.to_char(DailyReport.report_date, "YYYY-MM-DD")
    elif _is_sqlite():
        label_expr = func.strftime("%Y-%m", DailyReport.report_date)
    else:
        label_expr = func.to_char(DailyReport.report_date, "YYYY-MM")

    rows = (
        query.with_entities(label_expr.label("label"), func.count(DailyReport.id))
        .group_by("label")
        .order_by("label")
        .all()
    )
    return {"labels": [row[0] for row in rows], "counts": [row[1] for row in rows]}


def filtered_reports_query(filters):
    query = DailyReport.query.join(DailyReport.project)
    query = _apply_project_scope(query)
    if filters.get("project_id"):
        query = query.filter(DailyReport.project_id == filters["project_id"])
    if filters.get("from_date"):
        query = query.filter(DailyReport.report_date >= filters["from_date"])
    if filters.get("to_date"):
        query = query.filter(DailyReport.report_date <= filters["to_date"])
    if filters.get("overall_status"):
        query = query.filter(DailyReport.overall_status == filters["overall_status"])
    if filters.get("reporter"):
        query = query.filter(DailyReport.created_by_user_id == filters["reporter"])
    return query


def filtered_open_issues_query(filters):
    return filtered_issues_query(filters).filter(PersistentIssue.status.in_(OPEN_ISSUE_STATUSES))


def filtered_issues_query(filters):
    query = (
        PersistentIssue.query.filter(
            PersistentIssue.deleted_at.is_(None),
        )
        .join(PersistentIssue.project)
    )
    query = _apply_project_scope(query)
    if filters.get("project_id"):
        query = query.filter(PersistentIssue.project_id == filters["project_id"])
    if filters.get("from_date"):
        query = query.filter(PersistentIssue.opened_date >= filters["from_date"])
    if filters.get("to_date"):
        query = query.filter(PersistentIssue.opened_date <= filters["to_date"])
    if filters.get("overall_status") == DailyReportStatus.CRITICAL.value:
        query = query.filter(PersistentIssue.severity == IssueSeverity.CRITICAL.value)
    if filters.get("overall_status") == DailyReportStatus.PROCESSING.value:
        query = query.filter(PersistentIssue.status == IssueStatus.PROCESSING.value)
    return query


def accessible_reporters():
    query = User.query.filter(
        User.is_active.is_(True),
        User.deleted_at.is_(None),
    )
    project_ids = [project.id for project in accessible_projects_query().all()]
    query = query.join(ProjectUser, ProjectUser.user_id == User.id).filter(
        ProjectUser.project_id.in_(project_ids or [0]), ProjectUser.is_active.is_(True)
    )
    return query.order_by(User.full_name.asc()).all()


def _status_counts(query):
    rows = (
        query.with_entities(DailyReport.overall_status, func.count(DailyReport.id))
        .group_by(DailyReport.overall_status)
        .all()
    )
    return {status: count for status, count in rows}


def _apply_project_scope(query):
    query = query.filter(Project.deleted_at.is_(None))
    from app.project_memberships import accessible_project_ids
    ids = accessible_project_ids(current_user, ("can_view_project",))
    if ids is not None:
        query = query.filter(Project.id.in_(ids or [0]))
    return query


def _parse_date(value, field_name):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise DashboardFilterError(f"{field_name} phải đúng định dạng YYYY-MM-DD.") from exc


def _is_sqlite():
    from app.extensions import db

    return db.engine.name == "sqlite"
