"""The version-controlled permission catalogue.

Database rows are deliberately synchronised by an explicit CLI command, rather
than implicitly at application startup.
"""
from app.models.enums import UserRole

SYSTEM_ROLES = {
    UserRole.SUPER_ADMIN.value: "Quản trị tổng",
    UserRole.ADMIN.value: "Quản trị viên",
    UserRole.VIEWER_ADMIN.value: "Quản trị viên chỉ xem",
}

_RESOURCES = {
    "reports": "Báo cáo ngày", "attachments": "Tệp đính kèm", "report_attachments": "Ảnh báo cáo", "issues": "Vấn đề xuyên suốt",
    "projects": "Dự án", "categories": "Đầu mục báo cáo", "partners": "Đối tác",
    "companies": "Công ty", "fields": "Trường dữ liệu", "collections": "Bộ trường dữ liệu",
    "relations": "Quan hệ", "modules": "Phân hệ", "partner_companies": "Công ty đối tác",
    "partner_fields": "Trường dữ liệu đối tác", "partner_field_collections": "Bộ trường dữ liệu",
    "partner_relations": "Quan hệ đối tác", "users": "Người dùng", "roles": "Vai trò & phân quyền",
    "security": "Bảo mật", "system": "Hệ thống", "project_assignments": "Phân quyền dự án",
    "project_documents": "Hồ sơ tài liệu dự án", "project_document_folders": "Thư mục hồ sơ", "project_document_files": "Tệp hồ sơ",
    "company_media": "Thư viện ảnh/video công ty", "company_media_albums": "Album công ty", "company_media_files": "Media công ty",
    "storage": "Dung lượng & băng thông",
    "settings": "Cấu hình giao diện",
    "project_operations": "Quản lý dự án & đối tác",
    "customers": "Khách hàng",
    "project_contractors": "Đối tác dự án",
    "contractor_assignments": "Liên kết đối tác",
    "project_updates": "Báo cáo xuyên suốt",
    "construction_progress": "Tiến độ thi công",
    "dashboards": "Dashboard quản trị",
}

def _permission(code, name, *, dangerous=False, sort_order=0):
    resource, action = code.split(".", 1)
    return {"code": code, "name": name, "description": name, "module": resource,
            "group_name": _RESOURCES[resource], "resource": resource, "action": action,
            "sort_order": sort_order, "is_dangerous": dangerous, "is_deprecated": False}

PERMISSIONS = [
    *[_permission(f"{resource}.{action}", f"{action.title()} {_RESOURCES[resource]}", dangerous=action == "delete")
      for resource in ("reports", "attachments", "issues", "projects", "categories", "partners", "companies", "fields", "collections", "relations")
      for action in ("view", "create", "edit", "delete")],
    *[_permission(f"{resource}.manage", f"Quản lý {_RESOURCES[resource]}", dangerous=True)
      for resource in ("projects", "categories")],
    _permission("issues.close", "Đóng/mở lại Vấn đề xuyên suốt"),
    *[_permission(f"report_attachments.{action}", f"{action.title()} Ảnh báo cáo", dangerous=action == "delete")
      for action in ("view", "download", "delete")],
    _permission("users.view", "Xem người dùng"),
    _permission("users.manage", "Quản lý người dùng", dangerous=True),
    _permission("roles.view", "Xem vai trò và phân quyền"),
    _permission("roles.manage", "Quản lý vai trò và phân quyền", dangerous=True),
    _permission("security.audit", "Xem nhật ký bảo mật", dangerous=True),
    _permission("system.settings", "Cấu hình hệ thống", dangerous=True),
    _permission("project_assignments.manage", "Quản lý phân quyền dự án", dangerous=True),
    _permission("modules.reports.access", "Truy cập phân hệ Quản lý dự án"),
    _permission("modules.partners.access", "Truy cập phân hệ Quản lý đối tác"),
    _permission("modules.project_documents.access", "Truy cập phân hệ Hồ sơ tài liệu dự án"),
    _permission("project_documents.custom_roots.create", "Tạo mục hồ sơ tài liệu khác", dangerous=True),
    _permission("modules.company_media.access", "Truy cập phân hệ Thư viện ảnh/video công ty"),
    *[_permission(f"project_document_folders.{action}", f"{action.title()} Thư mục hồ sơ", dangerous=action in {"delete", "share"}) for action in ("view", "create", "edit", "delete", "share", "restore")],
    *[_permission(f"project_document_files.{action}", f"{action.title()} Tệp hồ sơ", dangerous=action == "delete") for action in ("view", "upload", "edit", "delete", "download", "restore")],
    *[_permission(f"company_media_albums.{action}", f"{action.title()} Album công ty", dangerous=action in {"delete", "share"}) for action in ("view", "create", "edit", "delete", "restore", "share")],
    *[_permission(f"company_media_files.{action}", f"{action.title()} Media công ty", dangerous=action == "delete") for action in ("view", "upload", "download", "edit", "delete", "restore")],
    *[_permission(f"partner_companies.{action}", f"{action.title()} Công ty đối tác", dangerous=action == "delete") for action in ("view", "create", "edit", "delete")],
    _permission("partners.restore", "Khôi phục Đối tác", dangerous=True),
    _permission("partner_companies.restore", "Khôi phục Công ty đối tác", dangerous=True),
    *[_permission(f"partner_fields.{action}", f"{action.title()} Trường dữ liệu đối tác") for action in ("view", "manage")],
    *[_permission(f"partner_field_collections.{action}", f"{action.title()} Bộ trường dữ liệu") for action in ("view", "manage")],
    *[_permission(f"partner_relations.{action}", f"{action.title()} Quan hệ đối tác", dangerous=action == "delete") for action in ("view", "manage", "delete")],
    _permission("storage.dashboard.view", "Xem Dung lượng & băng thông"),
    _permission("storage.dashboard.export", "Xuất Dung lượng & băng thông"),
    _permission("storage.dashboard.manage", "Quản lý Dung lượng & băng thông", dangerous=True),
    _permission("settings.branding.view", "Xem nhận diện hệ thống"),
    _permission("settings.branding.manage", "Quản lý nhận diện hệ thống", dangerous=True),
    _permission("reports.today.view", "Xem Hôm nay"),
    _permission("project_operations.view", "Xem Quản lý dự án & đối tác"),
    _permission("reports.configuration.view", "Xem cấu hình Báo cáo"),
    _permission("projects.scope_all", "Xem tất cả dự án trong phạm vi Báo cáo"),
    *[_permission(f"dashboards.{action}.view", f"Xem Dashboard {label}")
      for action, label in (
          ("system", "toàn hệ thống"),
          ("customer", "khách hàng"),
          ("project", "dự án"),
          ("contractor", "đối tác"),
          ("progress", "tiến độ thi công"),
      )],
    *[_permission(f"customers.{action}", f"{label} Khách hàng", dangerous=action == "archive")
      for action, label in (("view", "Xem"), ("create", "Tạo"), ("edit", "Sửa"), ("archive", "Lưu trữ"))],
    *[_permission(f"project_contractors.{action}", f"{label} Đối tác dự án", dangerous=action == "archive")
      for action, label in (("view", "Xem"), ("create", "Tạo"), ("edit", "Sửa"), ("archive", "Lưu trữ"))],
    _permission("contractor_assignments.view", "Xem liên kết đối tác"),
    _permission("contractor_assignments.manage", "Quản lý liên kết đối tác", dangerous=True),
    _permission("contractor_assignments.end", "Gỡ liên kết đối tác khỏi dự án", dangerous=True),
    *[_permission(f"project_updates.{action}", f"{label} Báo cáo xuyên suốt", dangerous=action == "delete")
      for action, label in (("view", "Xem"), ("create", "Tạo"), ("edit", "Sửa"), ("edit_all", "Sửa tất cả"), ("delete", "Xóa"))],
    *[_permission(f"construction_progress.{action}", f"{label} Tiến độ thi công", dangerous=action in {"delete", "structure"})
      for action, label in (("view", "Xem"), ("create", "Tạo phiếu"), ("edit", "Sửa phiếu của mình"), ("edit_all", "Sửa mọi phiếu"), ("delete", "Xóa phiếu"), ("structure", "Quản lý cấu trúc"))],
]

DEFAULTS = {
    UserRole.ADMIN.value: {p["code"] for p in PERMISSIONS if p["code"] not in {"roles.view", "roles.manage", "system.settings", "storage.dashboard.export", "storage.dashboard.manage", "settings.branding.view", "settings.branding.manage"}},
    UserRole.VIEWER_ADMIN.value: {
        *{p["code"] for p in PERMISSIONS if p["action"] == "view" and p["code"] != "roles.view"},
        "modules.reports.access",
        "modules.partners.access",
        "modules.project_documents.access", "project_document_folders.view", "project_document_files.view", "project_document_files.download",
        "modules.company_media.access", "company_media_albums.view", "company_media_files.view", "company_media_files.download",
        "storage.dashboard.view",
        "reports.today.view", "project_operations.view", "projects.scope_all",
        "dashboards.system.view", "dashboards.customer.view", "dashboards.project.view", "dashboards.contractor.view", "dashboards.progress.view",
        "customers.view", "project_contractors.view", "contractor_assignments.view", "project_updates.view",
    },
    UserRole.SUPER_ADMIN.value: set(),  # bypass; grants intentionally meaningless
}
