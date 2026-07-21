"""The version-controlled permission catalogue.

Database rows are deliberately synchronised by an explicit CLI command, rather
than implicitly at application startup.
"""
from app.models.enums import UserRole

SYSTEM_ROLES = {
    UserRole.SUPER_ADMIN.value: "Quản trị tổng",
    UserRole.ADMIN.value: "Quản trị viên",
    UserRole.VIEWER_ADMIN.value: "Quản trị viên chỉ xem",
    UserRole.PROJECT_MANAGER.value: "Quản lý dự án",
    UserRole.REPORTER.value: "Người báo cáo",
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
    _permission("modules.reports.access", "Truy cập phân hệ Báo cáo hàng ngày"),
    _permission("modules.partners.access", "Truy cập phân hệ Quản lý đối tác"),
    _permission("modules.project_documents.access", "Truy cập phân hệ Hồ sơ tài liệu dự án"),
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
]

DEFAULTS = {
    UserRole.ADMIN.value: {p["code"] for p in PERMISSIONS if p["code"] not in {"roles.view", "roles.manage", "system.settings"}},
    UserRole.VIEWER_ADMIN.value: {
        *{p["code"] for p in PERMISSIONS if p["action"] == "view" and p["code"] != "roles.view"},
        "modules.reports.access",
        "modules.partners.access",
        "modules.project_documents.access", "project_document_folders.view", "project_document_files.view", "project_document_files.download",
        "modules.company_media.access", "company_media_albums.view", "company_media_files.view", "company_media_files.download",
    },
    UserRole.PROJECT_MANAGER.value: {
        "modules.reports.access", "reports.view", "reports.create", "reports.edit",
        "issues.view", "issues.create", "issues.edit", "issues.close",
        "projects.view", "categories.view", "report_attachments.view", "report_attachments.delete",
        "modules.project_documents.access", "project_document_folders.view", "project_document_folders.create", "project_document_folders.edit",
        "project_document_files.view", "project_document_files.upload", "project_document_files.edit", "project_document_files.download",
    },
    UserRole.REPORTER.value: {
        "modules.reports.access", "reports.view", "reports.create", "reports.edit",
        "issues.view", "projects.view", "categories.view", "report_attachments.view", "report_attachments.delete",
        "modules.project_documents.access", "project_document_folders.view", "project_document_files.view", "project_document_files.upload", "project_document_files.download",
    },
    UserRole.SUPER_ADMIN.value: set(),  # bypass; grants intentionally meaningless
}
