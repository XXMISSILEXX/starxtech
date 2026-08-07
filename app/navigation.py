"""Request-first navigation policy; session is only a landing fallback."""
from flask import request, session, url_for

from app.auth.permissions import (can_access_company_media_module,
    can_access_project_documents_module, can_access_reports_module)


# These endpoints retain their existing URLs for compatibility, but they are
# permanently part of the Reports/project-management shell.  Keeping this
# policy in one place prevents a direct URL from rendering a different sidebar
# from the same link reached through /reports/config.
PROJECT_CONFIGURATION_ENDPOINT_PREFIXES = (
    "admin.projects_",
    "admin.categories_",
    "admin.memberships_",
    "customers.",
    "project_operations.contractors_",
    "project_operations.contractor_",
)


def is_project_configuration_endpoint(endpoint=None):
    endpoint = endpoint or request.endpoint or ""
    return endpoint == "admin.projects_reporters" or endpoint.startswith(PROJECT_CONFIGURATION_ENDPOINT_PREFIXES)


def is_project_domain_endpoint(endpoint=None):
    endpoint = endpoint or request.endpoint or ""
    return is_project_configuration_endpoint(endpoint) or endpoint.startswith("project_operations.")


def is_project_operations_overview_endpoint(endpoint=None):
    """Whether the project-operations overview is the only sidebar owner."""
    endpoint = endpoint or request.endpoint or ""
    return (endpoint.startswith("project_operations.")
            and not is_project_configuration_endpoint(endpoint)
            and endpoint != "project_operations.project_updates_index")


def get_active_module():
    blueprint = request.blueprint or ""
    if is_project_domain_endpoint():
        return "reports"
    mapping = {
        "partners": "partners", "partner_companies": "partners", "partner_fields": "partners",
        "partner_field_collections": "partners", "partner_relations": "partners",
        "project_documents": "project_documents", "company_media": "company_media",
        "admin": "admin", "admin_storage": "admin", "audit_log": "admin", "account": "account",
        "dashboard": "reports", "dashboard_api": "reports", "projects": "reports", "reports": "reports",
        "issues": "reports", "attachments": "reports", "customers": "reports", "project_operations": "reports", "construction_progress": "reports",
    }
    return mapping.get(blueprint, session.get("active_module", "reports"))


def get_sidebar_items(user, active_module=None):
    active_module = active_module or get_active_module()
    items = []
    current_endpoint = request.endpoint or ""

    def add(label, endpoint, icon, permission=None, *, desktop_active=False, mobile_active=None):
        allowed = permission if isinstance(permission, bool) else permission is None or user.can(permission)
        if allowed:
            items.append({
                "label": label,
                "url": url_for(endpoint),
                "icon": icon,
                "endpoint": endpoint,
                "desktop_active": desktop_active,
                "mobile_active": desktop_active if mobile_active is None else mobile_active,
            })
    if active_module == "reports":
        if user.can("dashboards.system.view") and user.can("projects.scope_all"):
            add("Dashboard quản trị", "dashboard.system_dashboard", "bi-grid-1x2",
                desktop_active=current_endpoint.startswith("dashboard.") or current_endpoint == "projects.dashboard")
        add("Hôm nay", "reports.today", "bi-calendar-check", "reports.today.view",
            desktop_active=current_endpoint == "reports.today")
        add("Tất cả báo cáo ngày", "reports.index", "bi-journal-text", can_access_reports_module(user),
            desktop_active=current_endpoint == "reports.index")
        add("Tất cả báo cáo xuyên suốt", "project_operations.project_updates_index", "bi-list-check", "project_updates.view",
            desktop_active=current_endpoint == "project_operations.project_updates_index")
        add("Quản lý dự án & đối tác", "project_operations.operations_index", "bi-diagram-3", "project_operations.view",
            desktop_active=is_project_operations_overview_endpoint(current_endpoint))
        add("Cấu hình", "reports.configuration_hub", "bi-gear", "reports.configuration.view",
            desktop_active=current_endpoint == "reports.configuration_hub" or is_project_configuration_endpoint(current_endpoint))
    elif active_module == "partners":
        add("Tổng quan đối tác", "partners.dashboard", "bi-grid-1x2", "partners.view",
            desktop_active=current_endpoint == "partners.dashboard")
        add("Đối tác", "partners.index", "bi-person-vcard", "partners.view",
            desktop_active=current_endpoint.startswith("partners.") and current_endpoint != "partners.dashboard")
        add("Công ty", "partner_companies.index", "bi-buildings", "partner_companies.view",
            desktop_active=current_endpoint.startswith("partner_companies."))
        add("Trường dữ liệu đối tác", "partner_fields.index", "bi-sliders", "partner_fields.view",
            desktop_active=current_endpoint.startswith("partner_fields."))
        add("Bộ trường dữ liệu", "partner_field_collections.index", "bi-collection", "partner_field_collections.view",
            desktop_active=current_endpoint.startswith("partner_field_collections."))
        add("Sơ đồ quan hệ", "partner_relations.index", "bi-diagram-3", "partner_relations.view",
            desktop_active=current_endpoint.startswith("partner_relations."))
    elif active_module == "project_documents":
        add("Hồ sơ dự án", "project_documents.index", "bi-folder2-open", can_access_project_documents_module(user),
            desktop_active=True)
    elif active_module == "company_media":
        add("Thư viện ảnh/video công ty", "company_media.index", "bi-images", can_access_company_media_module(user),
            desktop_active=True)
    elif active_module == "admin":
        add("Người dùng", "admin.users_index", "bi-people", "users.view",
            mobile_active=current_endpoint.startswith("admin.users"))
        add("Dung lượng & băng thông", "admin_storage.index", "bi-device-ssd", "storage.dashboard.view",
            mobile_active=current_endpoint.startswith("admin_storage."))
        add("Lịch sử thao tác", "audit_log.index", "bi-journal-text", "audit_logs.view",
            desktop_active=current_endpoint.startswith("audit_log."))
        add("Vai trò & phân quyền", "admin.roles_index", "bi-shield-lock", "roles.view",
            desktop_active=request.path.startswith("/admin/roles"))
        add("Nhận diện hệ thống", "admin.branding", "bi-palette", "settings.branding.view")
    return items
