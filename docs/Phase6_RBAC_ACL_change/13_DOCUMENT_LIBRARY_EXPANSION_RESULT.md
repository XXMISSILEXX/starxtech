# Phase 6.3 — Document Library expansion

The UI now calls the module “Hồ sơ tài liệu” while preserving the existing blueprint, URLs, permission codes, and storage namespace. Folder roots have `root_type`: project roots remain generated per project and project-scoped by membership; custom roots have no project and use global document RBAC plus inherited folder ACL.

`project_documents.custom_roots.create` permits creating custom top-level document areas. Custom roots support the same child folders, files, archive/restore, and folder ACL inheritance as project roots. This phase does not rename internal routes, add file-level ACL, ZIP downloads, or storage namespace changes.
