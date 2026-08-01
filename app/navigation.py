"""Request-first navigation policy; session is only a landing fallback."""
from flask import request, session, url_for


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


def get_active_module():
    blueprint = request.blueprint or ""
    if is_project_domain_endpoint():
        return "reports"
    mapping = {
        "partners": "partners", "partner_companies": "partners", "partner_fields": "partners",
        "partner_field_collections": "partners", "partner_relations": "partners",
        "project_documents": "project_documents", "company_media": "company_media",
        "admin": "admin", "admin_storage": "admin", "account": "account",
        "dashboard": "reports", "dashboard_api": "reports", "projects": "reports", "reports": "reports",
        "issues": "reports", "attachments": "reports", "customers": "reports", "project_operations": "reports", "construction_progress": "reports",
    }
    return mapping.get(blueprint, session.get("active_module", "reports"))


def get_sidebar_items(user, active_module=None):
    active_module = active_module or get_active_module()
    items = []
    def add(label, endpoint, icon, permission=None):
        if permission is None or user.can(permission):
            items.append({"label": label, "url": url_for(endpoint), "icon": icon, "endpoint": endpoint})
    if active_module == "reports":
        if user.can("dashboards.system.view") and user.can("projects.scope_all"):
            add("Dashboard quản trị", "dashboard.system_dashboard", "bi-grid-1x2")
        add("Hôm nay", "reports.today", "bi-calendar-check", "reports.today.view")
        add("Quản lý dự án & đối tác", "project_operations.operations_index", "bi-diagram-3", "project_operations.view")
        add("Cấu hình", "reports.configuration_hub", "bi-gear", "reports.configuration.view")
    elif active_module == "partners":
        add("Tổng quan đối tác", "partners.dashboard", "bi-grid-1x2", "partners.view")
        add("Đối tác", "partners.index", "bi-person-vcard", "partners.view")
        add("Công ty", "partner_companies.index", "bi-buildings", "partner_companies.view")
        add("Trường dữ liệu đối tác", "partner_fields.index", "bi-sliders", "partner_fields.view")
        add("Bộ trường dữ liệu", "partner_field_collections.index", "bi-collection", "partner_field_collections.view")
        add("Sơ đồ quan hệ", "partner_relations.index", "bi-diagram-3", "partner_relations.view")
    elif active_module == "project_documents":
        add("Hồ sơ tài liệu", "project_documents.index", "bi-folder2-open", "modules.project_documents.access")
    elif active_module == "company_media":
        add("Thư viện ảnh/video công ty", "company_media.index", "bi-images", "modules.company_media.access")
    elif active_module == "admin":
        add("Người dùng", "admin.users_index", "bi-people", "users.view")
        add("Dung lượng & băng thông", "admin_storage.index", "bi-device-ssd", "storage.dashboard.view")
        add("Vai trò & phân quyền", "admin.roles_index", "bi-shield-lock", "roles.view")
        add("Nhận diện hệ thống", "admin.branding", "bi-palette", "settings.branding.view")
    return items
