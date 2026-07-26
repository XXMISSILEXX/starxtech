# Navigation and module boundaries

**VERIFIED.** `app/modules/routes.py::select_reports/select_partners/select_admin` writes `session['active_module']`; `app/navigation.py::get_active_module` is request-blueprint-first and only falls back to session. `get_sidebar_items` produces sidebar links by active module and `User.can`; `app/__init__.py::inject_shell_context` sends them to `templates/base.html`.

Reports sidebar now has Bảng điều khiển, Dự án, Báo cáo. Partner sidebar has its own overview, partner/company/field/relationship links. Direct URLs are not protected by hiding links: global module guard and per-route helpers enforce access.

**Recommendation (TARGET):** place Hôm nay, Quản lý dự án & nhà thầu, Dashboard quản trị, Cấu hình in Reports-module navigation, because all existing Reports routes map to active module `reports`; retain global module selection as the cross-module boundary. Do not put project Customer/contractor functions in Partner navigation.

**Absolute boundary VERIFIED:** Partner models are `Company`, `CompanyDepartment`, `Partner`, `PartnerFieldDefinition/Value`, `PartnerRelationship` (`app/models/partner.py`) and prefixes `/partners`, `/partner-companies`, `/partner-fields`, `/partner-relations`; their permissions begin `partners`, `partner_companies`, etc. Geleximco/Handico/Taseco must be new project Customers; VTS/HT Hyundai/ZTSS/LogiTech must be new project contractors.
