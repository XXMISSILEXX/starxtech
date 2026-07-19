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
    "reports": "Báo cáo ngày", "attachments": "Tệp đính kèm", "issues": "Vấn đề xuyên suốt",
    "projects": "Dự án", "categories": "Đầu mục báo cáo", "partners": "Đối tác",
    "companies": "Công ty", "fields": "Trường dữ liệu", "collections": "Bộ trường dữ liệu",
    "relations": "Quan hệ", "users": "Người dùng", "roles": "Vai trò & phân quyền",
    "security": "Bảo mật", "system": "Hệ thống", "project_assignments": "Phân quyền dự án",
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
    _permission("users.manage", "Quản lý người dùng", dangerous=True),
    _permission("roles.view", "Xem vai trò và phân quyền"),
    _permission("roles.manage", "Quản lý vai trò và phân quyền", dangerous=True),
    _permission("security.audit", "Xem nhật ký bảo mật", dangerous=True),
    _permission("system.settings", "Cấu hình hệ thống", dangerous=True),
    _permission("project_assignments.manage", "Quản lý phân quyền dự án", dangerous=True),
]

DEFAULTS = {
    UserRole.ADMIN.value: {p["code"] for p in PERMISSIONS if p["code"] not in {"roles.view", "roles.manage", "system.settings"}},
    UserRole.VIEWER_ADMIN.value: {p["code"] for p in PERMISSIONS if p["action"] == "view" and p["code"] != "roles.view"},
    UserRole.PROJECT_MANAGER.value: {p["code"] for p in PERMISSIONS if p["resource"] in {"reports", "attachments", "issues", "projects", "categories"} and p["action"] in {"view", "create", "edit"}},
    UserRole.REPORTER.value: {p["code"] for p in PERMISSIONS if p["resource"] in {"reports", "attachments"} and p["action"] in {"view", "create", "edit"}},
    UserRole.SUPER_ADMIN.value: set(),  # bypass; grants intentionally meaningless
}
