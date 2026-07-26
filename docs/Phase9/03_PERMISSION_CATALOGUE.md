# Permission catalogue and role inventory

## Existing registry/DB codes (100)

`attachments.{create,delete,edit,view}`, `categories.{create,delete,edit,manage,view}`, `collections.{create,delete,edit,view}`, `companies.{create,delete,edit,view}`, `company_media_albums.{create,delete,edit,restore,share,view}`, `company_media_files.{delete,download,edit,restore,upload,view}`, `fields.{create,delete,edit,view}`, `issues.{close,create,delete,edit,view}`, `modules.{company_media.access,partners.access,project_documents.access,reports.access}`, `partner_companies.{create,delete,edit,restore,view}`, `partner_field_collections.{manage,view}`, `partner_fields.{manage,view}`, `partner_relations.{delete,manage,view}`, `partners.{create,delete,edit,restore,view}`, `project_assignments.manage`, `project_document_files.{delete,download,edit,restore,upload,view}`, `project_document_folders.{create,delete,edit,restore,share,view}`, `project_documents.custom_roots.create`, `projects.{create,delete,edit,manage,view}`, `relations.{create,delete,edit,view}`, `report_attachments.{delete,download,view}`, `reports.{create,delete,edit,view}`, `roles.{manage,view}`, `security.audit`, `settings.branding.{manage,view}`, `storage.dashboard.{export,manage,view}`, `system.settings`, `users.{manage,view}`.

Existing project-scope capabilities (not registry codes) are report view/create/edit-own/edit-all/archive, issue view/create/edit/close-reopen, category manage, and document capabilities in `ProjectUser`.

## Planned codes — not registered or granted in Step 9.0

- Navigation/config: `reports.today.view`, `project_operations.view`, `reports.configuration.view`.
- Scope/dashboard: `projects.scope_all`, `dashboards.system.view`, `dashboards.customer.view`, `dashboards.project.view`, `dashboards.contractor.view`.
- Customer: `customers.view/create/edit/archive`.
- Contractor: `project_contractors.view/create/edit/archive`.
- Assignment: `contractor_assignments.view/manage/end`.
- Project updates: `project_updates.view/create/edit/edit_all/delete`.

Step 9.1 must reconcile this list against the then-current registry, add only missing non-duplicate codes, and never reset existing DB grants blindly.

## DB role inventory (read-only)

| Role | Grant count |
| --- | ---: |
| `005` | 10 |
| `ADMIN` | 93 |
| `PARTNER` | 18 |
| `PROJECT_MANAGER` | 31 |
| `PROJECT_STAFF` | 0 |
| `REPORTER` | 17 |
| `SUPER_ADMIN` | 0 (policy bypass) |
| `VIEWER_ADMIN` | 27 |

Authorization for new routes will require authenticated/active user, Reports module access, action permission, and project scope where applicable. Custom role behavior must depend on permission code, never a custom role string.
