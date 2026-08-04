# ENDPOINTS-g5.md

Scope: endpoints added in `fc1a117..e764509` and existing endpoints whose
server-side authorisation, storage-delivery, state transition, error contract or
returned data changed in that delta. This is a delta matrix; unchanged endpoint
rows remain in `ENDPOINTS.md` and `ENDPOINTS-g1..g4.md`.

Foundation facts re-verified against the current source:

- `require_login` is app-wide (`app/__init__.py:154-168`). The public allow-list
  is exactly `auth.login`, `health`, `healthz`, and `static` (`:153`); no row
  below is public.
- The global reports-module hook is prefix based (`app/__init__.py:170-190`):
  only endpoint names beginning `dashboard.`, `dashboard_api.`, `projects.`,
  `reports.`, `issues.`, `attachments.`, `customers.`, or
  `project_operations.` (plus the listed admin project/category names) match.
  The “Global reports prefix?” column records that exact mechanism, not whether
  a module has some other guard.
- CSRFProtect is app-wide (`app/extensions.py:11`, initialised in
  `app/__init__.py:72`). POST rows are CSRF-covered; no changed endpoint is
  exempt. No changed package has a new `@limiter.limit` decorator.

| Method | Path | Endpoint / handler (file:line) | Blueprint | Decorator / authz | Global reports prefix? | RBAC / module gate | Project capability / object scope | CSRF | Rate limit | Changed behavior and storage notes |
|---|---|---|---|---|---|---|---|---|---|---|
| GET | `/branding/logo` | `branding.logo` → `app/branding.py:25-43`, registered `app/__init__.py:103-104` | direct app rule | `@login_required` | **No** — `branding.` is not in tuple | Login only; intentional system-wide branding read | N/A; resolves singleton active logo, never an ID supplied by browser | N/A | No | **New.** Redirects to signed S3 logo when cache is disabled; otherwise authorises first and serves only the active logo through `CacheSource`. No original path is exposed to anonymous users. |
| POST | `/account/preferences` | `account.save_preferences` (`app/account/routes.py:39-58`) | `account` | `@login_required` | **No** | Login-only self-service | Target is `current_user`; allow-lists appearance/accent in `account/preferences.py:8-30` | Yes | No | **New.** Persists only two validated values and writes an audit log; JSON/HTML response negotiation does not widen authority. |
| GET | `/account/avatar` | `account.avatar` (`app/account/routes.py:76-98`) | `account` | `@login_required` | **No** | Login-only | Current user's avatar relation only; checks active/non-deleted object | N/A | No | **Changed.** Cache-enabled path uses a hashed, authorised `CacheSource`; cache-disabled path retains no-store signed redirect. |
| GET | `/attachments/<attachment_id>/thumbnail` | `attachments.thumbnail` (`app/attachments/routes.py:45-66`) | `attachments` | global login + `_authorised()` | **Yes** | reports-module gate | `can_view_report` on attachment → section → report, never URL project ID | N/A | No | **Changed.** Generated thumbnail can use private cache; only derivative is cached/served. Processing fallback stays local static placeholder, not original. |
| POST | `/reports/<report_id>/edit` | `reports.edit` (`app/reports/routes.py:116-145`); `update_report` (`services.py:375-402`) | `reports` | global login; `_require_can_read`; POST `_require_can_write` | **Yes** | reports-module gate | `can_view_report` then `can_edit_report`; report/project is loaded server-side | Yes | No | **Changed.** Server validates submitted section IDs and attachment deletion IDs against this report; fixed per-section limit is now 10 (`reports/constants.py:7`). See `REPORTS-007` in findings. |
| GET | `/reports/<report_id>/edit` | `reports.edit` (`app/reports/routes.py:116-145`) | `reports` | global login + `_require_can_read` | **Yes** | reports-module gate | `can_view_report` | N/A | No | **Changed.** Emits server section IDs, client section IDs, active attachments and direct-upload limit contract for edit UI. |
| GET | `/reports/<report_id>` | `reports.detail` (`app/reports/routes.py:104-113`) | `reports` | global login + `_require_can_read` | **Yes** | reports-module gate | `can_view_report`; template now reflects changed attachment count | N/A | No | **Changed presentation only.** No broadened read scope found. |
| GET/POST | `/admin/projects/new` | `admin.projects_new` → `_save_project` (`app/admin/routes.py:214-226, 552-639`) | `admin` | `@permission_required("projects.manage")` on route | **Yes** — named admin exception | `projects.manage`; customer assignment additionally requires `customers.edit` | New customer must be active and `can_access_customer` + `can_manage_customer`; project has no existing customer on create | POST yes | No | **Changed.** Customer link is server-validated; no client-selected customer can be linked outside actor scope. |
| GET/POST | `/admin/projects/<project_id>/edit` | `admin.projects_edit` → `_save_project` (`app/admin/routes.py:229-240, 552-639`) | `admin` | `@permission_required("projects.manage")` | **Yes** — named admin exception | `projects.manage`, and `customers.edit` for customer change | Requires management of both prior and requested active customer; project is server-loaded | POST yes | No | **Changed.** Prevents the Phase-10 customer-move scope regression through the alternative admin form. |
| POST | `/customers/<customer_id>/projects/attach` | `customers.attach_project_from_form` (`app/customers/routes.py:251-256`) | `customers` | global login + `_permission_required("customers.edit")` in helper | **Yes** | reports-module gate + `customers.edit` | Target customer active/manageable; supplied project must be unclassified and `can_manage_project_scope` (`:217-246`) | Yes | No | **New.** Form variant delegates to one helper, preserving both customer and project scope checks. |
| POST | `/customers/<customer_id>/projects/<project_id>/attach` | `customers.attach_project` (`app/customers/routes.py:259-260`) | `customers` | same delegated helper | **Yes** | reports-module gate + `customers.edit` | Same server checks as form route; URL pair is revalidated | Yes | No | **New.** REST-shaped variant; not a second weaker implementation. |
| GET | `/project-documents/folders/<folder_id>` | `project_documents.folder` (`app/project_documents/routes.py:92-125`) | `project_documents` | blueprint `before_request require_module` (`:28-30`) + inline view check | **No** — own gate is intentional | `can_access_project_documents` | `can_view_project_document_folder`; per-child/file flags recomputed server-side | N/A | No | **Changed.** Publishes only derivative version IDs/URLs for files already in the authorised listing and powers folder-action UI. |
| POST | `/project-documents/files/<file_id>/signed-download` | `project_documents.signed_download` (`routes.py:174-183`); `create_file_download_url` (`services.py:258-287`) | `project_documents` | own module guard + `can_download_project_document_file` | **No** — own gate is intentional | documents module gate | File loaded server-side; download capability is file/folder/project scoped | Yes | No | **Changed.** Normalises unavailable/provider failure to signed-download contract without returning provider exception text. |
| GET | `/project-documents/files/<file_id>/thumbnail` | `project_documents.thumbnail` (`routes.py:194-221`) | `project_documents` | own module guard + `can_view_project_document_file` | **No** — own gate is intentional | documents module gate | File is server-loaded and view-authorised; active file/object and derivative rechecked | N/A | No | **New.** Serves only image thumbnail/video poster; cache path is authorised before fill and never serves original/PDF/ZIP. |
| POST | `/project-documents/folders/<folder_id>/files/complete-upload` | `project_documents.complete_upload` (`routes.py:161-171`); service `:226-256` | `project_documents` | own module guard + upload capability | **No** — own gate is intentional | documents module gate | Item is verified to belong to the loaded folder before shared completion | Yes | No | **Changed.** Existing `ProjectDocumentFile` prevents duplicate media-job enqueue on an idempotent completion replay. |
| GET | `/company-media/albums/<album_id>` | `company_media.album` (`app/company_media/routes.py:59-68`) | `company_media` | blueprint `guard` (`:41-43`) + `p.view_album` | **No** — own gate is intentional | Company Media module gate | Album ACL; no project capability model | N/A | No | **Changed.** Sends server-resolved upload limits and only authorized thumbnail version IDs. |
| POST | `/company-media/albums/<album_id>/files/upload-selection-sessions` | `company_media.selection` (`routes.py:113-119`) | `company_media` | own gate + `p.upload_album` | **No** | Company Media module gate | Album upload ACL; server creates session bound to actor/album | Yes | No | **Changed.** Enforces positive Company Media selection count/bytes from server configuration. |
| POST | `/company-media/albums/<album_id>/files/presign-batch` | `company_media.presign` (`routes.py:98-112`); storage service `:85-228,353-533` | `company_media` | own gate + `p.upload_album` | **No** | Company Media module gate | Locked selection is bound to creator, `company_media/album`, and album ID | Yes | No | **Changed.** Per-file/batch/selection limits; DB uniqueness/replay for `(selection_session_id, client_file_id)`; provider failures are sanitised. Browser data never selects key/bucket. |
| POST | `/company-media/albums/<album_id>/files/upload-selection-sessions/<session_id>/finalize` | `company_media.selection_finalize` (`routes.py:120-127`); storage `:542-601` | `company_media` | own gate + `p.upload_album` | **No** | Company Media module gate | Locks and binds session to actor+album; validates item IDs before status transition | Yes | No | **Changed.** Provides idempotent completed replay and typed cancelled/expired errors. |
| POST | `/company-media/albums/<album_id>/upload-sessions/<session_id>/cancel` | `company_media.selection_cancel` (`routes.py:128-144`); `upload_cleanup.py:82-183` | `company_media` | own gate + `p.upload_album`; service owner-or-admin check | **No** | Company Media module gate | Session lock verifies `company_media/album`, album ID, owner or ADMIN/SUPER_ADMIN | Yes | No | **New.** Database-only cancellation preserves completed media, serialises races and removes only proven unreferenced pending DB rows. It deliberately does not delete raw S3 bytes; see accepted operational risk `CM-OP-001`. |
| POST | `/company-media/albums/<album_id>/files/complete-upload` | `company_media.complete` (`routes.py:145-159`); service `:168-209` | `company_media` | own gate + `p.upload_album` | **No** | Company Media module gate | Item target is checked against loaded album; shared completion locks item/object and verifies owner/admin | Yes | No | **Changed.** Handles validation/not-found errors safely; CompanyMediaFile creation is savepoint/unique-constraint idempotent and enqueue occurs only for a newly created media row. |
| GET | `/company-media/files/<file_id>/thumbnail` | `company_media.thumbnail` (`routes.py:166-179`) | `company_media` | own gate + `p.view_file` | **No** | Company Media module gate | File loaded server-side and ACL checked; active object and derivative rechecked | N/A | No | **New.** Derivatives only (thumbnail/poster), private cache optional; missing derivative returns placeholder, never original. |
| POST | `/company-media/files/<file_id>/signed-download` | `company_media.download` (`routes.py:180-188`); `signed_download` (`services.py:234-254`) | `company_media` | own gate + `p.download_file` | **No** | Company Media module gate | File/album ACL and active original object rechecked before signing | Yes | No | **Changed.** Returns common `{ok,url,...}` contract and safe provider/source failures; signer does not use derivatives. |

## New/changed endpoint conclusions

- **Unauthenticated paths:** none. The new logo route is additionally decorated
  with `login_required`; all other rows pass the app-wide hook and are absent
  from the four public endpoint names.
- **Missing global reports prefix:** expected for `branding.`, `account.`,
  `company_media.` and `project_documents.`. The latter two have their own
  blueprint module gates. `branding` and `account` are not report modules.
  No changed reports-module route was found under an unrecognised endpoint
  prefix.
- **No new unauthorised object lookup:** every newly introduced item/session/file
  ID is either bound to its loaded parent and actor or is self-only. The customer
  attachment variants share the same target/source checks.
- **Rate-limit gap retained as a risk, not a missing auth finding:** expensive
  presign, cache-fill and cancellation paths have no per-route limit. Existing
  authenticated/module/ACL checks remain the admission control. Capacity and
  S3 billing must therefore be verified in staging under the selected limits.

