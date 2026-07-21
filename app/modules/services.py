from flask import url_for

from app.auth.permissions import (can_access_partners_module, can_access_project_documents_module,
    can_access_reports_module)
from app.company_media import permissions as company_media_permissions


MODULES = (
    ("reports", "Báo cáo hàng ngày", "Theo dõi dự án, báo cáo ngày và vấn đề tồn đọng.", "bi-journal-text"),
    ("partners", "Quản lý đối tác", "Quản lý đối tác, công ty và thông tin mở rộng.", "bi-person-vcard"),
    ("project_documents", "Hồ sơ dự án", "Quản lý thư mục và hồ sơ tài liệu theo dự án.", "bi-folder2-open"),
    ("company_media", "Thư viện ảnh/video công ty", "Album truyền thông nội bộ.", "bi-images"),
)


def get_accessible_modules(user):
    """Return module cards from one policy source; route authorization remains separate."""
    access = {
        "reports": can_access_reports_module(user),
        "partners": can_access_partners_module(user),
        "project_documents": can_access_project_documents_module(user),
        "company_media": company_media_permissions.access(user),
    }
    reasons = {
        "company_media": "scoped_acl" if company_media_permissions.has_album_acl(user)
                         and not company_media_permissions.has_module_access(user) else "role_access",
    }
    urls = {
        "reports": url_for("modules.select_reports"),
        "partners": url_for("modules.select_partners"),
        "project_documents": url_for("project_documents.index"),
        "company_media": url_for("company_media.index"),
    }
    return [{"key": key, "label": label, "description": description, "icon": icon,
             "url": urls[key], "reason": reasons.get(key, "role_access")}
            for key, label, description, icon in MODULES if access[key]]
