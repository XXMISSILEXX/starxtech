from datetime import datetime

from flask_login import current_user
from sqlalchemy import func

from app.models import (
    DailyReport,
    DailyReportStatus,
    IssueStatus,
    PersistentIssue,
    Project,
    ProjectUser,
    User,
    UserRole,
)
from app.reports.services import accessible_projects_query


OPEN_ISSUE_STATUSES = [IssueStatus.OPEN.value, IssueStatus.PROCESSING.value]


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
        raise DashboardFilterError("Invalid report status filter.")
    return filters


def dashboard_context(filters):
    reports = filtered_reports_query(filters)
    issues = filtered_open_issues_query(filters)
    status_counts = _status_counts(reports)

    return {
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
            "open_issues": issues.count(),
        },
        "latest_reports": reports.order_by(
            DailyReport.report_date.desc(),
            DailyReport.id.desc(),
        )
        .limit(10)
        .all(),
        "open_issues": issues.order_by(
            PersistentIssue.severity.desc(),
            PersistentIssue.opened_date.desc(),
            PersistentIssue.id.desc(),
        )
        .limit(10)
        .all(),
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
        }
    )
    return context


def status_chart_data(filters):
    counts = _status_counts(filtered_reports_query(filters))
    labels = [status.value for status in DailyReportStatus]
    return {"labels": labels, "counts": [counts.get(label, 0) for label in labels]}


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
    query = DailyReport.query.filter(DailyReport.deleted_at.is_(None)).join(DailyReport.project)
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
    query = (
        PersistentIssue.query.filter(
            PersistentIssue.deleted_at.is_(None),
            PersistentIssue.status.in_(OPEN_ISSUE_STATUSES),
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
    return query


def accessible_reporters():
    query = User.query.filter(
        User.is_active.is_(True),
        User.role == UserRole.REPORTER.value,
        User.deleted_at.is_(None),
    )
    if current_user.role == UserRole.REPORTER.value:
        project_ids = [project.id for project in accessible_projects_query().all()]
        query = query.join(ProjectUser, ProjectUser.user_id == User.id).filter(
            ProjectUser.project_id.in_(project_ids or [0])
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
    if current_user.role == UserRole.REPORTER.value:
        query = query.join(ProjectUser, ProjectUser.project_id == Project.id).filter(
            ProjectUser.user_id == current_user.id
        )
    return query


def _parse_date(value, field_name):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise DashboardFilterError(f"{field_name} must use YYYY-MM-DD format.") from exc


def _is_sqlite():
    from app.extensions import db

    return db.engine.name == "sqlite"
