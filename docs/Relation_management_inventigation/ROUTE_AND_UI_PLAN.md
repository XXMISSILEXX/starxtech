# Route and UI plan

## Routes phase implement

| Entity | Current | Proposed | Compatibility |
| --- | --- | --- | --- |
| Partner list | `GET /partners/` | `GET /partners?status=active|archived|all` | Giữ URL, default active. |
| Partner archive | `POST /partners/<id>/deactivate` | `POST /partners/<id>/archive` | Giữ old POST alias tạm thời, redirect/canonical link mới. |
| Partner restore | none | `POST /partners/<id>/restore` | New. |
| Company list | `GET /partner-companies/` | `GET /partner-companies?status=active|archived|all` | Giữ URL. |
| Company archive | `POST /partner-companies/<id>/deactivate` | `POST /partner-companies/<id>/archive` | Giữ old POST alias tạm thời. |
| Company restore | none | `POST /partner-companies/<id>/restore` | New. |
| Department archive/restore | current `.../delete` only | `POST .../archive`, `POST .../restore` | Old POST alias only if integrations require. |
| Relationship archive/restore | current `.../delete` only | `POST /partner-relations/<id>/archive`, `POST /partner-relations/<id>/restore` | Prefer company-scoped compatibility alias. |

Every proposed mutation uses POST + CSRF, `permission_required`, module guard,
status-aware resource lookup, audit and PRG redirect. Do not use GET aliases
for mutation.

## UI

Partner/Company list: segmented tabs or select for Đang hoạt động, Đã lưu trữ,
Tất cả; preserve all other filter parameters. Active row gets “Lưu trữ”; archived
row gets “Khôi phục”; all view gets status badge. View-only users see no action.

Partner detail: archived badge, disabled edit/archive actions where policy
requires, and Company archived badge. Company detail: archived badge and
warning; no create Department/manage Relationship action while Company inactive.
Company list must expose the archive action guarded by `partner_companies.delete`
(the current route exists but the reviewed list/detail UI does not expose it).

Forms: Create Partner selects only active Company/Department. Edit Partner adds
the current inactive Company/Department as a selected, labelled historical
option; validation permits unchanged historical link but blocks choosing a new
inactive value. Create Department and Department edit mutations reject inactive
Company. Flash messages: “Đã lưu trữ …”, “Đã khôi phục …”, and explicit warning
when Company must be restored first.
