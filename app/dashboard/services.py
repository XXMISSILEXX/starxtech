from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from zoneinfo import ZoneInfo

from flask_login import current_user
from sqlalchemy import String, and_, case, cast, func, literal, or_, select, union_all
from sqlalchemy.orm import joinedload

from app.models import (
    DailyReport,
    DailyReportStatus,
    DailyReportSection,
    IssueSeverity,
    IssueStatus,
    PersistentIssue,
    Customer,
    Project,
    ProjectContractor,
    ProjectStatus,
    ProjectContractorAssignment,
    ProjectContractorAssignmentStatus,
    ProjectUpdate,
    ProgressEntry,
    ProgressGroup,
    ProgressItem,
    ProgressType,
    SectionStatus,
)
from app.extensions import db
from app.ui import ASSIGNMENT_STATUS_LABELS, CONTRACTOR_ROLE_LABELS
from app.construction_progress.services import local_today, type_progress_summary
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
PROJECT_STATUS_LABELS = {
    ProjectStatus.ACTIVE.value: "Đang hoạt động",
    ProjectStatus.PAUSED.value: "Tạm dừng",
    ProjectStatus.COMPLETED.value: "Hoàn thành",
    ProjectStatus.ARCHIVED.value: "Lưu trữ",
}
PROJECT_ACTIVITY_PERIODS = (7, 30, 90)
PROJECT_ACTIVITY_DEFAULT_DAYS = 30
PROGRESS_DASHBOARD_PAGE_SIZE = 50
PROGRESS_STATUS_ORDER = {
    "overdue": 0,
    "in_progress": 1,
    "not_started": 2,
    "done": 3,
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


def scope_dashboard_projects(scope, capability=None):
    """Return project IDs allowed for one dashboard resource type.

    Dashboard access grants a surface only.  Resource rows are then narrowed
    by their own canonical project capability before any aggregate is built.
    """
    query = scope.projects_query()
    if capability:
        from app.project_memberships import accessible_project_ids

        project_ids = accessible_project_ids(current_user, (capability,))
        if project_ids is not None:
            query = query.filter(Project.id.in_(project_ids or [0]))
    return [project_id for (project_id,) in query.with_entities(Project.id).all()]


def _can_view_project_updates(project_id):
    """ProjectUpdate's canonical route policy: module grant plus project read."""
    from app.project_memberships import user_has_project_capability

    can = getattr(current_user, "can", None)
    return bool(
        callable(can)
        and can("project_updates.view")
        and user_has_project_capability(current_user, project_id, "can_view_project")
    )


class DashboardFilterError(ValueError):
    pass


def project_dashboard_context(project):
    """Project Dashboard data is intentionally independent of retired legacy aggregates."""
    from app.project_memberships import user_has_project_capability

    can_view_reports = user_has_project_capability(current_user, project.id, "can_view_reports")
    can_view_issues = user_has_project_capability(current_user, project.id, "can_view_issues")
    can_view_progress = user_has_project_capability(current_user, project.id, "can_view_progress")
    can_view_updates = _can_view_project_updates(project.id)
    reports = DailyReport.query.filter(DailyReport.project_id == project.id).order_by(
        DailyReport.report_date.desc(),
        DailyReport.id.desc(),
    )
    report_history = reports.limit(RECENT_DASHBOARD_LIMIT).all() if can_view_reports else []
    report_history_total = reports.order_by(None).count() if can_view_reports else 0
    # Keep aggregation independent from the report-history ordering. PostgreSQL
    # rejects an ORDER BY report_date on this GROUP BY overall_status query.
    rows = (
        db.session.query(DailyReport.overall_status, func.count(DailyReport.id))
        .filter(DailyReport.project_id == project.id)
        .group_by(DailyReport.overall_status)
        .order_by(DailyReport.overall_status)
        .all() if can_view_reports else []
    )
    status_counts = {status: int(count) for status, count in rows}
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
    recent_updates = recent_updates_query.limit(RECENT_DASHBOARD_LIMIT).all() if can_view_updates else []
    return {
        "project": project,
        "report_history": report_history,
        "report_history_total": report_history_total,
        "report_dates": [report.report_date for report in report_history],
        "project_dashboard": project_dashboard_metrics(
            project,
            include_reports=can_view_reports,
            include_issues=can_view_issues,
            include_updates=can_view_updates,
        ),
        "can_view_reports": can_view_reports,
        "can_view_issues": can_view_issues,
        "can_view_updates": can_view_updates,
        "progress_dashboard": project_progress_dashboard_context(project) if can_view_progress else None,
        "open_issues": open_issues,
        "recent_updates": recent_updates,
        "recent_updates_total": recent_updates_query.order_by(None).count() if can_view_updates else 0,
        "cards": {
            "total_reports": sum(status_counts.values()),
            "good_reports": status_counts.get(DailyReportStatus.GOOD.value, 0),
            "processing_reports": status_counts.get(DailyReportStatus.PROCESSING.value, 0),
            "attention_reports": status_counts.get(DailyReportStatus.ATTENTION.value, 0),
            "critical_reports": status_counts.get(DailyReportStatus.CRITICAL.value, 0),
        },
    }


def project_progress_dashboard_context(project):
    """Build project-progress dashboard data from eagerly loaded progress records."""
    progress_types = ProgressType.query.options(
        joinedload(ProgressType.groups).joinedload(ProgressGroup.items)
    ).filter(
        ProgressType.project_id == project.id,
    ).order_by(ProgressType.display_order, ProgressType.id).all()
    item_ids = [item.id for progress_type in progress_types for group in progress_type.groups for item in group.items]
    entries_by_item_id = {item_id: [] for item_id in item_ids}
    entries = ProgressEntry.query.filter(
        ProgressEntry.project_id == project.id,
        ProgressEntry.progress_item_id.in_(item_ids or [0]),
    ).order_by(ProgressEntry.report_date, ProgressEntry.id).all()
    for entry in entries:
        entries_by_item_id[entry.progress_item_id].append(entry)
    summaries = [type_progress_summary(progress_type, entries_by_item_id) for progress_type in progress_types]
    summaries.sort(key=lambda summary: (
        summary["planned_start"] is None,
        summary["planned_start"] or date.max,
        summary["progress_type"].name.casefold(),
    ))
    return {
        "summaries": summaries,
        "active_types": sum(summary["status"] == "in_progress" for summary in summaries),
        "total_types": len(summaries),
        "overdue_items": sum(summary["overdue_items"] for summary in summaries),
        "undated_items": sum(summary["undated_items"] for summary in summaries),
        "last_entry_date": max(
            (summary["last_entry_date"] for summary in summaries if summary["last_entry_date"] is not None),
            default=None,
        ),
    }


def progress_dashboard_context(*, page=1, today=None):
    """Build the cross-project progress dashboard from SQL-paginated rows."""
    from app.project_memberships import accessible_project_ids

    today = today or local_today()
    scope_project_ids = accessible_project_ids(
        current_user,
        ("can_view_project", "can_view_progress"),
    )
    scope_filter = [] if scope_project_ids is None else [
        ProgressType.project_id.in_(scope_project_ids or [0]),
    ]
    type_scope = ProgressType.query.join(Project).filter(
        Project.deleted_at.is_(None),
        *scope_filter,
    )
    rollup = _progress_type_rollup()
    percent = case(
        (ProgressType.value_mode == "money", rollup.c.money_percent),
        else_=rollup.c.quantity_percent,
    )
    status_rank = case(
        (or_(percent.is_(None), rollup.c.planned_start.is_(None)), PROGRESS_STATUS_ORDER["not_started"]),
        (percent >= 100, PROGRESS_STATUS_ORDER["done"]),
        (rollup.c.planned_end < today, PROGRESS_STATUS_ORDER["overdue"]),
        (rollup.c.planned_start <= today, PROGRESS_STATUS_ORDER["in_progress"]),
        else_=PROGRESS_STATUS_ORDER["not_started"],
    )
    ordered_ids = type_scope.outerjoin(rollup, rollup.c.type_id == ProgressType.id).with_entities(
        ProgressType.id.label("type_id"),
    ).order_by(
        status_rank.asc(),
        rollup.c.planned_end.asc().nulls_last(),
        ProgressType.id.asc(),
    )
    total_rows = ordered_ids.order_by(None).count()
    type_ids = [row.type_id for row in ordered_ids.limit(PROGRESS_DASHBOARD_PAGE_SIZE).offset((page - 1) * PROGRESS_DASHBOARD_PAGE_SIZE).all()]
    progress_types = []
    entries_by_item_id = {}
    if type_ids:
        loaded_types = ProgressType.query.options(
            joinedload(ProgressType.project),
            joinedload(ProgressType.groups).joinedload(ProgressGroup.items),
        ).filter(ProgressType.id.in_(type_ids)).all()
        by_id = {progress_type.id: progress_type for progress_type in loaded_types}
        progress_types = [by_id[type_id] for type_id in type_ids]
        item_ids = [
            item.id
            for progress_type in progress_types
            for group in progress_type.groups
            for item in group.items
        ]
        entries_by_item_id = {item_id: [] for item_id in item_ids}
        entries = ProgressEntry.query.filter(
            ProgressEntry.progress_item_id.in_(item_ids or [0]),
        ).order_by(ProgressEntry.report_date, ProgressEntry.id).all()
        for entry in entries:
            entries_by_item_id[entry.progress_item_id].append(entry)
    summaries = [
        type_progress_summary(progress_type, entries_by_item_id, today=today)
        for progress_type in progress_types
    ]
    status_counts = dict(type_scope.outerjoin(rollup, rollup.c.type_id == ProgressType.id).with_entities(
        status_rank.label("status_rank"),
        func.count(ProgressType.id),
    ).group_by(status_rank).all())
    progress_project_ids = type_scope.with_entities(ProgressType.project_id).distinct().subquery()
    projects_with_progress = db.session.query(func.count()).select_from(progress_project_ids).scalar()
    overdue_types = status_counts.get(PROGRESS_STATUS_ORDER["overdue"], 0)
    overdue_items = _progress_dashboard_overdue_item_count(scope_filter, today)
    stale_projects = _progress_dashboard_stale_project_count(progress_project_ids, today)
    return {
        "summaries": summaries,
        "cards": {
            "projects_with_progress": projects_with_progress,
            "overdue_types": overdue_types,
            "overdue_items": overdue_items,
            "stale_projects": stale_projects,
        },
        "page": page,
        "page_size": PROGRESS_DASHBOARD_PAGE_SIZE,
        "total_rows": total_rows,
        "has_previous": page > 1,
        "has_next": page * PROGRESS_DASHBOARD_PAGE_SIZE < total_rows,
    }


def _progress_type_rollup():
    """Return a SQL rollup matching the planned bounds and type percent rules."""
    scheduled_start = case(
        (and_(ProgressItem.planned_start_date.is_not(None), ProgressItem.planned_end_date.is_not(None)), ProgressItem.planned_start_date),
        else_=None,
    )
    scheduled_end = case(
        (and_(ProgressItem.planned_start_date.is_not(None), ProgressItem.planned_end_date.is_not(None)), ProgressItem.planned_end_date),
        else_=None,
    )
    item_percent_value = case(
        (ProgressItem.planned_quantity > 0, ProgressItem.completed_quantity * 100 / ProgressItem.planned_quantity),
        else_=None,
    )
    group_rollup = select(
        ProgressGroup.progress_type_id.label("type_id"),
        func.min(scheduled_start).label("planned_start"),
        func.max(scheduled_end).label("planned_end"),
        func.avg(item_percent_value).label("quantity_percent"),
        func.sum(ProgressItem.planned_quantity).label("planned_quantity"),
        func.sum(ProgressItem.completed_quantity).label("completed_quantity"),
    ).join(ProgressItem, ProgressItem.progress_group_id == ProgressGroup.id).group_by(
        ProgressGroup.id,
        ProgressGroup.progress_type_id,
    ).subquery()
    return select(
        group_rollup.c.type_id,
        func.min(group_rollup.c.planned_start).label("planned_start"),
        func.max(group_rollup.c.planned_end).label("planned_end"),
        func.avg(group_rollup.c.quantity_percent).label("quantity_percent"),
        (func.sum(group_rollup.c.completed_quantity) * 100 / func.nullif(func.sum(group_rollup.c.planned_quantity), 0)).label("money_percent"),
    ).group_by(group_rollup.c.type_id).subquery()


def _progress_dashboard_overdue_item_count(scope_filter, today):
    return ProgressItem.query.join(ProgressGroup).join(ProgressType).join(Project).filter(
        Project.deleted_at.is_(None),
        *scope_filter,
        ProgressItem.planned_start_date.is_not(None),
        ProgressItem.planned_end_date.is_not(None),
        ProgressItem.planned_end_date < today,
        ProgressItem.planned_quantity > 0,
        ProgressItem.completed_quantity * 100 / ProgressItem.planned_quantity < 100,
    ).count()


def _progress_dashboard_stale_project_count(project_ids, today):
    latest_entries = db.session.query(
        ProgressEntry.project_id.label("project_id"),
        func.max(ProgressEntry.report_date).label("last_entry_date"),
    ).filter(ProgressEntry.project_id.in_(select(project_ids.c.project_id))).group_by(ProgressEntry.project_id).subquery()
    stale_before = today - timedelta(days=7)
    return Project.query.outerjoin(
        latest_entries,
        latest_entries.c.project_id == Project.id,
    ).filter(
        Project.id.in_(select(project_ids.c.project_id)),
        or_(
            latest_entries.c.last_entry_date.is_(None),
            latest_entries.c.last_entry_date < stale_before,
        ),
    ).count()


def project_dashboard_metrics(project, selected_date=None, days=7, *, include_reports=True,
                              include_issues=True, include_updates=True):
    """Project-only aggregates; section statuses remain their native five values."""
    selected_date = selected_date or datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
    statuses = [item.value for item in SectionStatus]
    rows = db.session.query(DailyReportSection.status, func.count(DailyReportSection.id)).join(
        DailyReport, DailyReport.id == DailyReportSection.daily_report_id
    ).filter(DailyReport.project_id == project.id, DailyReport.report_date == selected_date).group_by(DailyReportSection.status).all() if include_reports else []
    pie = {status: 0 for status in statuses}; pie.update(dict(rows))
    start = selected_date - timedelta(days=days - 1)
    trend_rows = db.session.query(DailyReport.report_date, DailyReportSection.status, func.count(DailyReportSection.id)).join(
        DailyReportSection, DailyReportSection.daily_report_id == DailyReport.id
    ).filter(DailyReport.project_id == project.id, DailyReport.report_date.between(start, selected_date)).group_by(DailyReport.report_date, DailyReportSection.status).order_by(DailyReport.report_date).all() if include_reports else []
    labels = [(start + timedelta(days=offset)).isoformat() for offset in range(days)]
    datasets = {status: [0] * len(labels) for status in statuses}; positions = {label: index for index, label in enumerate(labels)}
    for report_date, status, count in trend_rows: datasets[status][positions[report_date.isoformat()]] = count
    assignments = ProjectContractorAssignment.query.filter(
        ProjectContractorAssignment.project_id == project.id,
        ProjectContractorAssignment.status == ProjectContractorAssignmentStatus.ACTIVE.value,
    )
    issue_counts = dict(db.session.query(PersistentIssue.status, func.count(PersistentIssue.id)).filter(
        PersistentIssue.project_id == project.id, PersistentIssue.deleted_at.is_(None)
    ).group_by(PersistentIssue.status).all()) if include_issues else {}
    return {"selected_date": selected_date, "section_pie": pie, "section_trend": {"labels": labels, "datasets": datasets},
            "submitted_today": DailyReport.query.filter_by(project_id=project.id, report_date=selected_date).count() > 0 if include_reports else False,
            "construction_active": assignments.filter_by(role="CONSTRUCTION").count(), "solution_active": assignments.filter_by(role="SOLUTION").count(),
            "issue_counts": issue_counts, "latest_update": ProjectUpdate.query.filter(ProjectUpdate.project_id == project.id, ProjectUpdate.deleted_at.is_(None)).order_by(ProjectUpdate.update_date.desc(), ProjectUpdate.id.desc()).first() if include_updates else None}


def project_section_status_payload(project, selected_date=None):
    from app.project_memberships import user_has_project_capability

    can_view_reports = user_has_project_capability(current_user, project.id, "can_view_reports")
    can_view_issues = user_has_project_capability(current_user, project.id, "can_view_issues")
    can_view_updates = _can_view_project_updates(project.id)
    metrics = project_dashboard_metrics(
        project,
        selected_date=selected_date,
        include_reports=can_view_reports,
        include_issues=can_view_issues,
        include_updates=can_view_updates,
    )
    keys = [item.value for item in SectionStatus]
    labels = ["Thông tin", "Tốt", "Đang xử lý", "Cần chú ý", "Khẩn cấp"]
    values = [int(metrics["section_pie"][key]) for key in keys]
    latest = metrics["latest_update"]
    report = DailyReport.query.filter_by(project_id=project.id, report_date=metrics["selected_date"]).first() if can_view_reports else None
    return {"selected_date": metrics["selected_date"].isoformat(), "timezone": "Asia/Ho_Chi_Minh",
            "submission": {"submitted": report is not None, "report_id": report.id if report else None, "report_date": report.report_date.isoformat() if report else None},
            "section_status": {"labels": labels, "keys": keys, "values": values, "total": sum(values)},
            "trend": {"days": metrics["section_trend"]["labels"], "series": {key: [int(value) for value in metrics["section_trend"]["datasets"][key]] for key in keys}},
            "contractors": {"construction_active": metrics["construction_active"], "solution_active": metrics["solution_active"]},
            "persistent_issues": {"total": sum(metrics["issue_counts"].values()), "by_status": metrics["issue_counts"]},
            "latest_project_update": {"id": latest.id, "date": latest.update_date.isoformat(), "title": latest.title} if latest else None}


def dashboard_scope_context(scope, selected_date=None, days=7, *, include_recent=True):
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
    from app.project_memberships import is_project_admin, is_viewer_admin
    # Built-in admin read roles hold every canonical read capability.  Reusing
    # the already materialised base scope avoids duplicate scope queries while
    # custom roles still use their resource-specific capability query.
    read_all_resources = is_project_admin(current_user) or is_viewer_admin(current_user)
    report_project_ids = all_project_ids if read_all_resources else scope_dashboard_projects(scope, "can_view_reports")
    issue_project_ids = all_project_ids if read_all_resources else scope_dashboard_projects(scope, "can_view_issues")
    update_project_ids = all_project_ids if current_user.can("project_updates.view") else []
    report_active_project_ids = [project.id for project in active_projects if project.id in set(report_project_ids)]

    submitted_rows = []
    if report_active_project_ids:
        submitted_rows = (
            db.session.query(DailyReport.project_id, DailyReport.id, DailyReport.overall_status)
            .filter(
                DailyReport.project_id.in_(report_active_project_ids),
                DailyReport.report_date == selected_date,
            )
            .all()
        )
    reports_by_project = {project_id: {"id": report_id, "status": status} for project_id, report_id, status in submitted_rows}
    project_rows = [
        {
            "project": project,
            "report": reports_by_project.get(project.id) if project.id in report_project_ids else None,
            "submitted": project.id in reports_by_project if project.id in report_project_ids else None,
        }
        for project in active_projects
    ]
    recent_project_rows = [
        {"project": project, "report": reports_by_project.get(project.id) if project.id in report_project_ids else None,
         "submitted": project.id in reports_by_project if project.id in report_project_ids else None}
        for project in effective_projects.filter(Project.status == ProjectStatus.ACTIVE.value).order_by(Project.code).limit(RECENT_DASHBOARD_LIMIT).all()
    ]
    missing_projects = [row["project"] for row in project_rows if row["submitted"] is False]

    section_pie = _section_status_counts(report_active_project_ids, selected_date)
    section_trend = _section_status_trend(report_active_project_ids, selected_date, days)
    issue_counts = _issue_dashboard_counts(issue_project_ids)
    contractor_counts = _active_contractor_counts(all_project_ids)
    updates = _recent_project_updates(update_project_ids) if include_recent else []
    recent_updates_total = (ProjectUpdate.query.filter(ProjectUpdate.project_id.in_(update_project_ids or [0]), ProjectUpdate.deleted_at.is_(None)).count() if include_recent else 0)
    recent_reports = _recent_daily_reports(report_project_ids) if include_recent else []
    recent_reports_total = DailyReport.query.filter(DailyReport.project_id.in_(report_project_ids or [0])).count() if include_recent else 0

    expected_count = len(report_active_project_ids)
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
        "all_project_ids": all_project_ids,
        "report_project_ids": report_project_ids,
        "issue_project_ids": issue_project_ids,
        "update_project_ids": update_project_ids,
        "recent_projects": recent_project_rows,
        "active_projects_total": len(active_projects),
        "missing_projects": missing_projects,
        "recent_updates": updates,
        "recent_updates_total": recent_updates_total,
        "recent_reports": recent_reports,
        "recent_reports_total": recent_reports_total,
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
    context = dashboard_scope_context(scope, selected_date=selected_date, days=days, include_recent=False)
    section_keys = [item.value for item in SectionStatus]
    issue_status_keys = [item.value for item in IssueStatus]
    severity_keys = [item.value for item in IssueSeverity]
    report_rows = [row for row in context["projects"] if row["project"].id in context["report_project_ids"]]
    issue_rows = [row for row in context["projects"] if row["project"].id in context["issue_project_ids"]]
    project_labels = [row["project"].code for row in report_rows]
    payload = {
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
            "values": [1 if row["submitted"] else 0 for row in report_rows],
        },
        "overall_status": {
            "labels": project_labels,
            "keys": [row["report"]["status"] if row["report"] else None for row in report_rows],
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
                "labels": [row["project"].code for row in issue_rows],
                "values": [int(context["issue_counts"]["by_project"].get(row["project"].id, 0)) for row in issue_rows],
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
    # System-only analytics intentionally remain additive so the established
    # Customer contract keeps its compact scoped response.
    if scope.kind == DashboardScopeType.SYSTEM:
        payload["system_analytics"] = _system_dashboard_analytics(
            context["all_project_ids"],
            context["issue_project_ids"],
            context["report_project_ids"],
            [row["project"].id for row in report_rows if row["project"].status == ProjectStatus.ACTIVE.value],
            context["selected_date"],
        )
    return payload


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
    project_ids = [project_id for (project_id,) in assignment_query.with_entities(ProjectContractorAssignment.project_id).distinct().all()]
    report_project_ids = [project_id for project_id in project_ids if project_id in set(scope_dashboard_projects(DashboardScope.contractor(contractor.id), "can_view_reports"))]
    issue_project_ids = [project_id for project_id in project_ids if project_id in set(scope_dashboard_projects(DashboardScope.contractor(contractor.id), "can_view_issues"))]
    update_project_ids = project_ids if current_user.can("project_updates.view") else []
    latest_update = (
        ProjectUpdate.query.options(joinedload(ProjectUpdate.project))
        .filter(ProjectUpdate.contractor_assignment_id.in_(assignment_ids.select()), ProjectUpdate.project_id.in_(update_project_ids or [0]), ProjectUpdate.deleted_at.is_(None))
        .order_by(ProjectUpdate.update_date.desc(), ProjectUpdate.created_at.desc(), ProjectUpdate.id.desc())
        .first()
    )
    updates_total = ProjectUpdate.query.filter(ProjectUpdate.contractor_assignment_id.in_(assignment_ids.select()), ProjectUpdate.project_id.in_(update_project_ids or [0]), ProjectUpdate.deleted_at.is_(None)).count()
    updates = (
        ProjectUpdate.query.options(
            joinedload(ProjectUpdate.project),
            joinedload(ProjectUpdate.contractor_assignment).joinedload(ProjectContractorAssignment.contractor),
        )
        .filter(ProjectUpdate.contractor_assignment_id.in_(assignment_ids.select()), ProjectUpdate.project_id.in_(update_project_ids or [0]), ProjectUpdate.deleted_at.is_(None))
        .order_by(ProjectUpdate.update_date.desc(), ProjectUpdate.created_at.desc(), ProjectUpdate.id.desc())
        .limit(RECENT_DASHBOARD_LIMIT).all()
    )

    latest_report_dates = (
        db.session.query(DailyReport.project_id, func.max(DailyReport.report_date).label("report_date"))
        .filter(DailyReport.project_id.in_(report_project_ids or [0]))
        .group_by(DailyReport.project_id).subquery()
    )
    latest_reports = (
        DailyReport.query.options(joinedload(DailyReport.project))
        .join(latest_report_dates, (DailyReport.project_id == latest_report_dates.c.project_id) & (DailyReport.report_date == latest_report_dates.c.report_date))
        .order_by(DailyReport.report_date.desc(), DailyReport.id.desc()).limit(RECENT_DASHBOARD_LIMIT).all()
    )
    can_view_issues = bool(issue_project_ids)
    issues = (
        PersistentIssue.query.options(joinedload(PersistentIssue.project))
        .filter(PersistentIssue.project_id.in_(issue_project_ids or [0]), PersistentIssue.deleted_at.is_(None))
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
        "can_view_reports": bool(report_project_ids),
        "can_view_updates": bool(update_project_ids),
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


def _recent_daily_reports(project_ids):
    if not project_ids:
        return []
    return (
        DailyReport.query.options(
            joinedload(DailyReport.project).joinedload(Project.customer),
            joinedload(DailyReport.created_by),
        )
        .filter(DailyReport.project_id.in_(project_ids))
        .order_by(DailyReport.report_date.desc(), DailyReport.created_at.desc(), DailyReport.id.desc())
        .limit(RECENT_DASHBOARD_LIMIT)
        .all()
    )


def _system_dashboard_analytics(project_ids, issue_project_ids, report_project_ids, active_report_project_ids, selected_date):
    """Aggregate-only System Dashboard analytics within the effective scope."""
    total_projects = len(project_ids)
    project_scope = project_ids or [0]
    active_scope = active_report_project_ids or [0]
    issue_scope = issue_project_ids or [0]
    report_scope = report_project_ids or [0]
    id_text = lambda column: cast(column, String)
    activity_label = Project.code + literal(" · ") + Project.name
    statements = [
        select(literal("customer").label("kind"), func.coalesce(id_text(Project.customer_id), literal("unclassified")).label("entity"), func.coalesce(Customer.name, literal("Chưa phân loại")).label("label"), func.count(Project.id).label("count")).select_from(Project).outerjoin(Customer, Customer.id == Project.customer_id).where(Project.id.in_(project_scope)).group_by(Project.customer_id, Customer.name),
        select(literal("status"), Project.status, Project.status, func.count(Project.id)).select_from(Project).where(Project.id.in_(project_scope)).group_by(Project.status),
        select(literal("coverage"), id_text(ProjectContractor.id), ProjectContractor.name, func.count(func.distinct(ProjectContractorAssignment.project_id))).select_from(ProjectContractor).join(ProjectContractorAssignment, ProjectContractorAssignment.contractor_id == ProjectContractor.id).where(ProjectContractorAssignment.project_id.in_(active_scope), ProjectContractorAssignment.status == ProjectContractorAssignmentStatus.ACTIVE.value).group_by(ProjectContractor.id, ProjectContractor.name),
        select(literal("issues"), id_text(Project.id), activity_label, func.count(PersistentIssue.id)).select_from(Project).join(PersistentIssue, PersistentIssue.project_id == Project.id).where(Project.id.in_(issue_scope), PersistentIssue.deleted_at.is_(None), PersistentIssue.status.in_([IssueStatus.OPEN.value, IssueStatus.PROCESSING.value])).group_by(Project.id, Project.code, Project.name),
    ]
    for period in PROJECT_ACTIVITY_PERIODS:
        start = selected_date - timedelta(days=period - 1)
        statements.append(select(literal(f"reports_{period}"), id_text(Project.id), activity_label, func.count(DailyReport.id)).select_from(Project).join(DailyReport, DailyReport.project_id == Project.id).where(Project.id.in_(report_scope), DailyReport.report_date.between(start, selected_date)).group_by(Project.id, Project.code, Project.name))
    grouped = {}
    for kind, entity, label, count in db.session.execute(union_all(*statements)).all():
        grouped.setdefault(kind, []).append((entity, label, int(count)))
    customer_rows = sorted(grouped.get("customer", []), key=lambda row: (-row[2], row[1]))
    coverage_rows = sorted(grouped.get("coverage", []), key=lambda row: (-row[2], row[1]))[:10]
    issue_rows = sorted(grouped.get("issues", []), key=lambda row: (-row[2], row[1]))[:10]
    status_counts = {entity: count for entity, _label, count in grouped.get("status", [])}
    customer_share = {"labels": [label for _entity, label, _count in customer_rows], "values": [count for _entity, _label, count in customer_rows], "percentages": [round((count / total_projects) * 100, 1) if total_projects else 0 for _entity, _label, count in customer_rows], "total_projects": total_projects}
    status_keys = [status.value for status in ProjectStatus]
    project_status = {"keys": status_keys, "labels": [PROJECT_STATUS_LABELS[key] for key in status_keys], "values": [status_counts.get(key, 0) for key in status_keys], "percentages": [round((status_counts.get(key, 0) / total_projects) * 100, 1) if total_projects else 0 for key in status_keys], "total_projects": total_projects}
    coverage_denominator = len(active_report_project_ids)
    contractor_coverage = {
        "contractor_ids": [int(contractor_id) for contractor_id, _name, _count in coverage_rows],
        "labels": [name for _contractor_id, name, _count in coverage_rows], "values": [count for _contractor_id, _name, count in coverage_rows],
        "percentages": [round((count / coverage_denominator) * 100, 1) if coverage_denominator else 0 for _contractor_id, _name, count in coverage_rows],
        "denominator_active_projects": coverage_denominator,
        "note": "Một dự án có thể có nhiều đối tác đang hoạt động nên tổng tỷ lệ có thể vượt 100%.",
    }
    issue_activity = _activity_payload(issue_rows)
    report_periods = {str(period): _activity_payload(sorted(grouped.get(f"reports_{period}", []), key=lambda row: (-row[2], row[1]))[:10]) for period in PROJECT_ACTIVITY_PERIODS}
    return {
        "customer_project_share": customer_share,
        "contractor_project_coverage": contractor_coverage,
        "project_status_distribution": project_status,
        "project_activity": {
            "default_days": PROJECT_ACTIVITY_DEFAULT_DAYS,
            "current_issues": issue_activity,
            "daily_reports": {"periods": report_periods},
        },
    }


def _activity_payload(rows):
    values = [count for _project_id, _label, count in rows]
    total_count = sum(values)
    return {
        "project_ids": [int(project_id) for project_id, _label, _count in rows],
        "labels": [label for _project_id, label, _count in rows],
        "values": values,
        # Activity shares intentionally use the activity total, not the number
        # of projects in scope.  This keeps the value meaningful when one
        # project has multiple issues or reports.
        "total_count": total_count,
        "percentages": [round((count / total_count) * 100, 1) if total_count else 0 for count in values],
    }
