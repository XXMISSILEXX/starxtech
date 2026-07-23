import re

from markupsafe import Markup, escape

from app.models import DailyReportStatus, IssueSeverity, IssueStatus, SectionStatus, UserRole


ROLE_LABELS = {
    UserRole.SUPER_ADMIN.value: "Quản trị tổng",
    UserRole.ADMIN.value: "Quản trị",
    UserRole.VIEWER_ADMIN.value: "Quản trị chỉ xem",
    UserRole.PROJECT_MANAGER.value: "Quản lý dự án",
    UserRole.REPORTER.value: "Người báo cáo",
}

MODULE_LABELS = {
    "reports": "Báo cáo hàng ngày",
    "partners": "Quản lý đối tác",
    "project_documents": "Hồ sơ tài liệu",
    "company_media": "Thư viện ảnh/video công ty",
}

STATUS_LABELS = {
    DailyReportStatus.UPDATED.value: "Cập nhật",
    DailyReportStatus.GOOD.value: "Tốt",
    DailyReportStatus.PROCESSING.value: "Đang xử lý",
    DailyReportStatus.ATTENTION.value: "Cần chú ý",
    DailyReportStatus.CRITICAL.value: "Nghiêm trọng",
    SectionStatus.INFO.value: "Thông tin",
    IssueStatus.OPEN.value: "Đang mở",
    IssueStatus.RESOLVED.value: "Đã xử lý",
    IssueStatus.CLOSED.value: "Đã đóng",
    IssueSeverity.LOW.value: "Thấp",
    IssueSeverity.MEDIUM.value: "Trung bình",
    IssueSeverity.HIGH.value: "Cao",
}

STATUS_ICONS = {
    DailyReportStatus.UPDATED.value: "ℹ️",
    DailyReportStatus.GOOD.value: "✅",
    DailyReportStatus.PROCESSING.value: "⚠️",
    DailyReportStatus.ATTENTION.value: "⚠️",
    DailyReportStatus.CRITICAL.value: "🔴",
    SectionStatus.INFO.value: "ℹ️",
    IssueStatus.OPEN.value: "ℹ️",
    IssueStatus.PROCESSING.value: "⚠️",
    IssueStatus.RESOLVED.value: "✅",
    IssueStatus.CLOSED.value: "✅",
    IssueSeverity.LOW.value: "ℹ️",
    IssueSeverity.MEDIUM.value: "⚠️",
    IssueSeverity.HIGH.value: "⚠️",
    IssueSeverity.CRITICAL.value: "🔴",
}

ISSUE_SEVERITY_ICONS = {
    IssueSeverity.LOW.value: "🟢",
    IssueSeverity.MEDIUM.value: "🟡",
    IssueSeverity.HIGH.value: "🟠",
    IssueSeverity.CRITICAL.value: "🔴",
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


def role_label(role):
    return ROLE_LABELS.get(role, role or "-")


def module_label(module):
    return MODULE_LABELS.get(module, "Chưa chọn phân hệ")


def status_label(value):
    return STATUS_LABELS.get(value, value or "-")


def status_icon(value):
    return STATUS_ICONS.get(value, "ℹ️")


def status_tone(value):
    return STATUS_TONES.get(value, (value or "muted").lower())


def issue_severity_label(value):
    return f"{ISSUE_SEVERITY_ICONS.get(value, 'ℹ️')} {status_label(value)}"


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
    app.jinja_env.filters["status_icon"] = status_icon
    app.jinja_env.filters["status_tone"] = status_tone
    app.jinja_env.filters["issue_severity_label"] = issue_severity_label
    app.jinja_env.filters["issue_status_label"] = issue_status_label
    app.jinja_env.filters["vn_bytes"] = format_bytes
    app.jinja_env.globals["category_icon"] = category_icon
    app.jinja_env.globals["status_icon"] = status_icon
    app.jinja_env.globals["status_tone"] = status_tone
    app.jinja_env.globals["module_label"] = module_label
    app.jinja_env.globals["can_access_reports_module"] = can_access_reports_module
    app.jinja_env.globals["can_access_partners_module"] = can_access_partners_module
    app.jinja_env.globals["can_access_project_documents_module"] = can_access_project_documents_module
    app.jinja_env.globals["can_access_company_media_module"] = can_access_company_media_module
    app.jinja_env.globals["can_create_partner"] = can_create_partner
    app.jinja_env.globals["can_manage_partner_fields"] = can_manage_partner_fields
    app.jinja_env.globals["can_manage_users"] = can_manage_users
