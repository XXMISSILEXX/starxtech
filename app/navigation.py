"""Request-first navigation policy; session is only a landing fallback."""
from flask import request, session, url_for


def get_active_module():
    blueprint = request.blueprint or ""
    mapping = {
        "partners": "partners", "partner_companies": "partners", "partner_fields": "partners",
        "partner_field_collections": "partners", "partner_relations": "partners",
        "project_documents": "project_documents", "company_media": "company_media",
        "admin": "admin", "admin_storage": "admin", "account": "account",
        "dashboard": "reports", "dashboard_api": "reports", "projects": "reports", "reports": "reports",
        "issues": "reports", "attachments": "reports", "customers": "reports", "project_operations": "reports",
    }
    return mapping.get(blueprint, session.get("active_module", "reports"))


def get_sidebar_items(user, active_module=None):
    active_module = active_module or get_active_module()
    items = []
    def add(label, endpoint, icon, permission=None):
        if permission is None or user.can(permission):
            items.append({"label": label, "url": url_for(endpoint), "icon": icon, "endpoint": endpoint})
    if active_module == "reports":
        add("Hôm nay", "reports.today", "bi-calendar-check", "reports.today.view")
        add("Quản lý dự án & nhà thầu", "project_operations.operations_index", "bi-diagram-3", "project_operations.view")
        add("Dashboard quản trị", "dashboard.index", "bi-grid-1x2", "reports.view")
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
        add("Quản lý dự án", "admin.projects_index", "bi-kanban", "projects.view")
        add("Dung lượng & băng thông", "admin_storage.index", "bi-device-ssd", "storage.dashboard.view")
        add("Vai trò & phân quyền", "admin.roles_index", "bi-shield-lock", "roles.view")
        add("Nhận diện hệ thống", "admin.branding", "bi-palette", "settings.branding.view")
    return items
