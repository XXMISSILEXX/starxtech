import re

from markupsafe import Markup, escape

from app.models import DailyReportStatus, IssueSeverity, IssueStatus, SectionStatus, UserRole


ROLE_LABELS = {
    UserRole.SUPER_ADMIN.value: "Quản trị tổng",
    UserRole.VIEWER_ADMIN.value: "Quản trị chỉ xem",
    UserRole.PROJECT_MANAGER.value: "Quản lý dự án",
    UserRole.REPORTER.value: "Người báo cáo",
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


def role_label(role):
    return ROLE_LABELS.get(role, role or "-")


def status_label(value):
    return STATUS_LABELS.get(value, value or "-")


def category_icon(icon):
    value = (icon or "").strip()
    if not value:
        return Markup('<i class="bi bi-folder2-open"></i>')

    normalized = value[3:] if value.startswith("bi-") else value
    if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,48}", normalized):
        return Markup(f'<i class="bi bi-{escape(normalized)}"></i>')

    if len(value) <= 8:
        return Markup(f'<span class="category-emoji">{escape(value)}</span>')

    return Markup('<i class="bi bi-folder2-open"></i>')


def register_template_helpers(app):
    app.jinja_env.filters["role_label"] = role_label
    app.jinja_env.filters["status_label"] = status_label
    app.jinja_env.globals["category_icon"] = category_icon
