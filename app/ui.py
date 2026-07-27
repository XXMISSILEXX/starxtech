import re

from markupsafe import Markup, escape

from app.models import (
    DailyReportStatus,
    IssueSeverity,
    IssueStatus,
    ProjectStatus,
    ProjectContractorAssignmentStatus,
    ProjectContractorRole,
    ProjectUpdateType,
    SectionStatus,
    UserRole,
)
from app.date_utils import format_vn_date


ROLE_LABELS = {
    UserRole.SUPER_ADMIN.value: "Quản trị tổng",
    UserRole.ADMIN.value: "Quản trị",
    UserRole.VIEWER_ADMIN.value: "Quản trị chỉ xem",
    UserRole.PROJECT_MANAGER.value: "Quản lý dự án",
    UserRole.REPORTER.value: "Người báo cáo",
}

MODULE_LABELS = {
    "reports": "Quản lý dự án",
    "partners": "Quản lý đối tác",
    "project_documents": "Hồ sơ tài liệu",
    "company_media": "Thư viện ảnh/video công ty",
    "admin": "Quản trị hệ thống",
}

REPORT_STATUS_LABELS = {
    DailyReportStatus.UPDATED.value: "Cập nhật",
    DailyReportStatus.GOOD.value: "Tốt",
    DailyReportStatus.PROCESSING.value: "Đang xử lý",
    DailyReportStatus.ATTENTION.value: "Cần chú ý",
    DailyReportStatus.CRITICAL.value: "Khẩn cấp",
}

STATUS_LABELS = {
    **REPORT_STATUS_LABELS,
    SectionStatus.INFO.value: "Thông tin",
    IssueStatus.OPEN.value: "Đang mở",
    IssueStatus.RESOLVED.value: "Đã xử lý",
    IssueStatus.CLOSED.value: "Đã đóng",
    IssueSeverity.LOW.value: "Thấp",
    IssueSeverity.MEDIUM.value: "Trung bình",
    IssueSeverity.HIGH.value: "Cao",
    ProjectStatus.ACTIVE.value: "Đang hoạt động",
    ProjectStatus.PAUSED.value: "Tạm dừng",
    ProjectStatus.COMPLETED.value: "Hoàn thành",
    ProjectStatus.ARCHIVED.value: "Đã lưu trữ",
}

PROJECT_UPDATE_TYPE_LABELS = {
    ProjectUpdateType.GENERAL.value: "Cập nhật chung",
    ProjectUpdateType.PROGRESS.value: "Tiến độ",
    ProjectUpdateType.HANDOVER.value: "Bàn giao",
    ProjectUpdateType.CONTRACTOR.value: "Cập nhật đối tác",
    ProjectUpdateType.STATUS_CHANGE.value: "Thay đổi trạng thái",
    ProjectUpdateType.NOTE.value: "Ghi chú",
}
CONTRACTOR_ROLE_LABELS = {
    ProjectContractorRole.CONSTRUCTION.value: "Đối tác thi công",
    ProjectContractorRole.SOLUTION.value: "Đối tác giải pháp",
}
ASSIGNMENT_STATUS_LABELS = {
    ProjectContractorAssignmentStatus.ACTIVE.value: "Đang hoạt động",
    ProjectContractorAssignmentStatus.PAUSED.value: "Tạm dừng",
    ProjectContractorAssignmentStatus.COMPLETED.value: "Hoàn thành",
    ProjectContractorAssignmentStatus.ENDED.value: "Đã kết thúc",
}

STATUS_ICON_KEYS = {
    DailyReportStatus.UPDATED.value: "info-circle-fill",
    DailyReportStatus.GOOD.value: "check-circle-fill",
    DailyReportStatus.PROCESSING.value: "arrow-repeat",
    DailyReportStatus.ATTENTION.value: "exclamation-triangle-fill",
    DailyReportStatus.CRITICAL.value: "x-octagon-fill",
    SectionStatus.INFO.value: "info-circle-fill",
}


ISSUE_SEVERITY_ICONS = {
    IssueSeverity.LOW.value: "🟢",
    IssueSeverity.MEDIUM.value: "🟡",
    IssueSeverity.HIGH.value: "🟠",
    IssueSeverity.CRITICAL.value: "🔴",
}

ISSUE_SEVERITY_LABELS = {
    IssueSeverity.LOW.value: "Thấp",
    IssueSeverity.MEDIUM.value: "Trung bình",
    IssueSeverity.HIGH.value: "Cao",
    IssueSeverity.CRITICAL.value: "Nghiêm trọng",
}

ISSUE_STATUS_ICONS = {
    IssueStatus.OPEN.value: "🟡",
    IssueStatus.PROCESSING.value: "🔵",
    IssueStatus.RESOLVED.value: "✅",
    IssueStatus.CLOSED.value: "✅",
}

STATUS_TONES = {
    DailyReportStatus.UPDATED.value: "info",
    DailyReportStatus.GOOD.value: "good",
    DailyReportStatus.PROCESSING.value: "processing",
    DailyReportStatus.ATTENTION.value: "attention",
    DailyReportStatus.CRITICAL.value: "critical",
    SectionStatus.INFO.value: "info",
}

# A single presentation contract for every report/section status control and
# badge.  ``css_class`` remains a compatibility alias for existing templates.
STATUS_PRESENTATION = {
    value: {
        "value": value,
        "label": STATUS_LABELS[value],
        "tone": STATUS_TONES[value],
        "icon_key": STATUS_ICON_KEYS[value],
        "color_class": f"status-color-{STATUS_TONES[value]}",
        "background_class": f"status-bg-{STATUS_TONES[value]}",
        "css_class": f"status-{STATUS_TONES[value]}",
        "order": order,
    }
    for order, value in enumerate((
        DailyReportStatus.UPDATED.value,
        SectionStatus.INFO.value,
        DailyReportStatus.GOOD.value,
        DailyReportStatus.PROCESSING.value,
        DailyReportStatus.ATTENTION.value,
        DailyReportStatus.CRITICAL.value,
    ), start=1)
}


def role_label(role):
    return ROLE_LABELS.get(role, role or "-")


def module_label(module):
    return MODULE_LABELS.get(module, "Chưa chọn phân hệ")


def status_label(value):
    return STATUS_LABELS.get(value, value or "-")


def project_update_type_label(value):
    return PROJECT_UPDATE_TYPE_LABELS.get(value, value or "-")


def contractor_role_label(value):
    return CONTRACTOR_ROLE_LABELS.get(value, value or "-")


def assignment_status_label(value):
    return ASSIGNMENT_STATUS_LABELS.get(value, value or "-")


def vn_datetime(value):
    return value.strftime("%d/%m/%Y lúc %H:%M") if value else "—"


def status_icon(value):
    return STATUS_ICON_KEYS.get(value, "info-circle-fill")


def status_tone(value):
    return STATUS_TONES.get(value, (value or "muted").lower())


def status_presentation(value):
    return STATUS_PRESENTATION.get(value, {"value": value, "label": status_label(value), "tone": "muted", "icon_key": "info-circle-fill", "color_class": "status-color-muted", "background_class": "status-bg-muted", "css_class": "status-muted", "order": 999})


def issue_severity_label(value):
    return f"{ISSUE_SEVERITY_ICONS.get(value, 'ℹ️')} {ISSUE_SEVERITY_LABELS.get(value, value or '-') }"


def issue_status_label(value):
    return f"{ISSUE_STATUS_ICONS.get(value, 'ℹ️')} {status_label(value)}"


def category_icon(icon):
    value = (icon or "").strip()
    if not value:
        return Markup('<span class="category-emoji">📌</span>')

    normalized = value[3:] if value.startswith("bi-") else value
    if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,48}", normalized):
        return Markup(f'<i class="bi bi-{escape(normalized)}"></i>')

    if len(value) <= 8:
        return Markup(f'<span class="category-emoji">{escape(value)}</span>')

    return Markup('<span class="category-emoji">📌</span>')


def register_template_helpers(app):
    from app.admin_storage.services import format_bytes
    from app.auth.permissions import (
        can_access_partners_module,
        can_access_project_documents_module,
        can_access_company_media_module,
        can_access_reports_module,
        can_create_partner,
        can_manage_partner_fields,
        can_manage_users,
    )
    from app.partners.services import display_field_value, format_vn_date

    app.jinja_env.filters["role_label"] = role_label
    app.jinja_env.filters["module_label"] = module_label
    app.jinja_env.filters["partner_field_value"] = display_field_value
    app.jinja_env.filters["vn_date"] = format_vn_date
    app.jinja_env.filters["status_label"] = status_label
    app.jinja_env.filters["project_update_type_label"] = project_update_type_label
    app.jinja_env.filters["contractor_role_label"] = contractor_role_label
    app.jinja_env.filters["assignment_status_label"] = assignment_status_label
    app.jinja_env.filters["vn_datetime"] = vn_datetime
    app.jinja_env.filters["status_icon"] = status_icon
    app.jinja_env.filters["status_tone"] = status_tone
    app.jinja_env.filters["issue_severity_label"] = issue_severity_label
    app.jinja_env.filters["issue_status_label"] = issue_status_label
    app.jinja_env.filters["vn_bytes"] = format_bytes
    app.jinja_env.globals["category_icon"] = category_icon
    app.jinja_env.globals["status_icon"] = status_icon
    app.jinja_env.globals["status_tone"] = status_tone
    app.jinja_env.globals["status_presentation"] = status_presentation
    app.jinja_env.globals["module_label"] = module_label
    app.jinja_env.globals["can_access_reports_module"] = can_access_reports_module
    app.jinja_env.globals["can_access_partners_module"] = can_access_partners_module
    app.jinja_env.globals["can_access_project_documents_module"] = can_access_project_documents_module
    app.jinja_env.globals["can_access_company_media_module"] = can_access_company_media_module
    app.jinja_env.globals["can_create_partner"] = can_create_partner
    app.jinja_env.globals["can_manage_partner_fields"] = can_manage_partner_fields
    app.jinja_env.globals["can_manage_users"] = can_manage_users
    app.jinja_env.globals["static_asset_version"] = app.config.get("STATIC_ASSET_VERSION", "1")
