# Project and category configuration

**VERIFIED.** Project CRUD/archive is `app/admin/routes.py::projects_*`, gated by `projects.view/manage`; archive only changes `Project.status` to `archived`. Membership administration is `project_assignments.manage`, not PM capability. Categories are project-owned `ReportCategory`, unique by project/name (`app/models/project.py`), active/required/sorted/iconned, and routes `admin.categories_*` require project category helper.

Category creation is manual: `_save_project` does not create defaults. `categories_for_create` selects active, non-deleted categories. V2 validates category belongs to project and requires every supplied section unique by category, but does **not** generate sections nor enforce every active/required category. `is_required` is stored/form-editable but no finalize validation references it (**VERIFIED** via `app/reports/services.py::validate_daily_report_create_v2_payload`). Soft delete is allowed even if used; legacy sections retain FK and forms include used inactive categories. Rename/icon changes are read live through `section.report_category`, so historical labels/icons are not snapshot.

Conclusion: **do not add `ProjectReportItem`**; it duplicates `ReportCategory`. Future template-copy needs a separate template domain and explicit copy semantics, not another per-project item table.
