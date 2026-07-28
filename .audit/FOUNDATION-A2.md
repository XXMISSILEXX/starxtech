# FOUNDATION-A2.md — Data model & audit trail deep pass

Read-only. Scope: `app/models/` (all 19 files: `__init__.py`, `audit_log.py`,
`bulk_download.py`, `company_media.py`, `customer.py`, `daily_report.py`,
`enums.py`, `issue.py`, `media_processing.py`, `mixins.py`, `partner.py`,
`project.py`, `project_contractor.py`, `project_document.py`,
`project_update.py`, `rbac.py`, `storage.py`, `system_setting.py`,
`user.py`), `app/audit.py`, `app/date_utils.py`, `app/branding.py`,
`migrations/` (structural chain review + full read of 4 migrations chosen
for their consequence — not all 29 line-by-line, per instruction). Every
model file was read in full. One correction to Foundation-A1 is included
below (§4) since this pass's scope is what resolves it.

---

## 1. Every model — table, keys, nullability, constraints, indexes, cascades

39 model classes across 19 files. Full inventory (only non-obvious/
security-relevant columns called out per class; every FK's `ondelete` is
stated since that's what determines cascade behavior):

| Model | Table | PK | Notable FKs (`ondelete`) | Unique/Check | Notable nullable-vs-required |
|---|---|---|---|---|---|
| `AuditLog` | `audit_logs` | `id` BigInt | `actor_user_id`→`users.id` (default RESTRICT-equivalent, no `ondelete` specified) | none | `actor_user_id`/`entity_id`/`old_values_json`/`new_values_json`/`ip_address`/`user_agent` all nullable — an audit row with a null actor is valid (system/unauthenticated actions, e.g. failed login before a user is resolved) |
| `User` | `users` | `id` BigInt | `role_id`→`roles.id` (no explicit `ondelete`, so DB-default RESTRICT — a `Role` cannot be deleted while users reference it), `avatar_storage_object_id`→`storage_objects.id` (`SET NULL`) | `username`/`email` unique | `email` nullable (a user can have no email — confirm login-by-email path handles this; `auth/routes.py`'s `or_(User.username==..., User.email==...)` would simply never match a null email, which is safe) |
| `Project` | `projects` | `id` BigInt | `customer_id`→`customers.id` (`RESTRICT`) | `code` unique; `CheckConstraint` on `status` | `customer_id` nullable (a project can exist with no customer) |
| `ProjectUser` | `project_users` | `id` BigInt | `project_id`→`projects.id` (`CASCADE`), `user_id`→`users.id` (`CASCADE`) | `UniqueConstraint(project_id, user_id)` | all 16 `can_*` capability flags `nullable=False`, default `False` — **fail-closed by column default**, a newly inserted membership row grants nothing until explicitly set |
| `ReportCategory` | `report_categories` | `id` BigInt | `project_id`→`projects.id` (`CASCADE`) | `UniqueConstraint(project_id, name)` | — |
| `DailyReport` | `daily_reports` | `id` BigInt | `project_id`→`projects.id` (`CASCADE`) | `UniqueConstraint(project_id, report_date)`, `UniqueConstraint(project_id, client_request_id)`, `CheckConstraint` on `overall_status` | **No soft-delete column of any kind** (see §2 — this is deliberate, not an oversight, per migration `20260724_0023`) |
| `DailyReportSection` | `daily_report_sections` | `id` BigInt | `daily_report_id`→`daily_reports.id` (`CASCADE`), `report_category_id`→`report_categories.id` (no `ondelete` — RESTRICT-equivalent) | `UniqueConstraint(daily_report_id, report_category_id)` | a `ReportCategory` cannot be hard-deleted while any section references it (RESTRICT) — but `ReportCategory` uses soft-delete (`is_active`/`deleted_at`) in practice, so this RESTRICT is a backstop, not the primary retirement path |
| `ReportAttachment` | `report_attachments` | `id` BigInt | `daily_report_section_id`→`daily_report_sections.id` (`CASCADE`), `storage_object_id`→`storage_objects.id` (no `ondelete`) | — | `storage_object_id` nullable "for the explicit 0020 → CLI → 0021 transition" (comment, `daily_report.py:111-112`) — DB `CheckConstraint` `ck_report_attachments_active_storage_object` (added in migration `0021`, not visible in the model file itself — **model and migration agree here only if you read both**, flagged in §6) enforces `deleted_at IS NOT NULL OR storage_object_id IS NOT NULL` at the DB level, i.e., an *active* attachment row must have a storage object; this constraint is invisible from `app/models/daily_report.py` alone |
| `PersistentIssue` | `persistent_issues` | `id` BigInt | `project_id`→`projects.id` (`CASCADE`) | `CheckConstraint` on `severity`, `status` | `owner_user_id` nullable, `created_by_user_id` required |
| `Role` | `roles` | `id` (BigInt/Int per dialect) | — | `code` unique | no soft-delete at all — roles are never retired, only their grants (`RolePermission`) are |
| `Permission` | `permissions` | `id` | — | `code` unique | `is_deprecated` flag exists as a soft-retirement signal distinct from delete — a "deprecated" permission still physically exists and can theoretically still be granted unless application code checks the flag (not verified here, out of scope — `app/permissions/services.py` was A1 scope, not re-checked here) |
| `RolePermission` | `role_permissions` | `id` | `role_id`→`roles.id` (`CASCADE`), `permission_id`→`permissions.id` (`CASCADE`) | `UniqueConstraint(role_id, permission_id)` | pure join table, no timestamps, no soft-delete — a revoked grant is a real `DELETE`, not a flag flip; **hard-deleting a grant leaves no historical record of when/whether it existed**, except whatever `AuditLog` rows the calling code chose to write (not verified here — `app/admin/routes.py` is out of scope) |
| `StorageObject` | `storage_objects` | `id` (STORAGE_ID) | `uploaded_by_id`→`users.id` (no `ondelete`) | `UniqueConstraint(bucket, object_key)`, `CheckConstraint` on `upload_status` (includes literal value `'deleted'`) and `processing_status` | **carries both `SoftDeleteMixin`'s `deleted_at` AND an `upload_status` enum value literally named `'deleted'`** — two independent "this is gone" signals on the same row, see §2 |
| `UploadBatch` | `upload_batches` | `id` | `created_by_id`→`users.id`, `selection_session_id`→`upload_selection_sessions.id` | `CheckConstraint` on `module_type`/`target_type`/`status` | no soft-delete; `items` relationship cascades `all, delete-orphan` |
| `UploadSelectionSession` | `upload_selection_sessions` | `id` | `created_by_id`→`users.id` | `CheckConstraint` on `module_type`/`target_type`/`status` (includes `cancelled`/`expired`) | no soft-delete columns — lifecycle is entirely status-driven |
| `DownloadEvent` | `download_events` | `id` | `user_id`→`users.id`, `storage_object_id`→`storage_objects.id`, `derivative_id`→`storage_derivatives.id` | — | append-only event log, correctly has no soft-delete/update-shaped columns |
| `UploadBatchItem` | `upload_batch_items` | `id` | `upload_batch_id`→`upload_batches.id` (`CASCADE`), `storage_object_id`→`storage_objects.id` | `UniqueConstraint(upload_batch_id, client_file_id)`, `CheckConstraint` on `status` | `finalized_at` prevents double-consumption (comment: "prevents it being attached twice") — an application-level idempotency guard, not a DB unique constraint on the consumption event itself |
| `Company` | `companies` | `id` BigInt | `company_photo_storage_object_id`→`storage_objects.id` | — | `SoftDeleteMixin` + separate `is_active` — two flags, see §2 |
| `CompanyDepartment` | `company_departments` | `id` BigInt | `company_id`→`companies.id` (`CASCADE`), `parent_department_id`→`company_departments.id` (**`SET NULL`**, self-referential) | `UniqueConstraint(company_id, name)` | **no DB constraint prevents a department from being its own ancestor** — see §2/§6b cross-reference for unit 6b |
| `Partner` | `partners` | `id` BigInt | `company_id`→`companies.id` (no `ondelete`), `department_id`→`company_departments.id` (`SET NULL`) | — | `SoftDeleteMixin` + `is_active` — two flags |
| `PartnerFieldDefinition` | `partner_field_definitions` | `id` | — | `field_key` unique | no soft-delete beyond `is_active` |
| `PartnerFieldCollection` | `partner_field_collections` | `id` | — | — | `is_active` only |
| `PartnerFieldCollectionItem` | `partner_field_collection_items` | `id` | `collection_id`→...`.id` (`CASCADE`), `field_definition_id`→...`.id` (`CASCADE`) | `UniqueConstraint(collection_id, field_definition_id)` | no soft-delete at all — pure join-table semantics, hard delete only |
| `PartnerFieldValue` | `partner_field_values` | `id` | `partner_id`→`partners.id` (`CASCADE`), `field_definition_id`→...`.id` (no `ondelete`, nullable) | — | **snapshot-by-design** (`field_label_snapshot`/`field_key_snapshot`/`field_type_snapshot`/`group_name_snapshot` duplicate the definition's shape at write time) — this is exactly the "retain enough snapshot metadata" requirement from `CLAUDE.md`, confirmed implemented at the schema level, not just claimed |
| `PartnerRelationship` | `partner_relationships` | `id` BigInt | `from_partner_id`/`to_partner_id`/`partner_id`/`parent_partner_id`→`partners.id` (mixed `CASCADE`/`SET NULL`), `parent_relationship_id`→**self** (`SET NULL`) | — | **self-referential `parent_relationship_id` with no cycle-prevention constraint** — same shape of risk as `CompanyDepartment`, see §2/§6b |
| `Customer` | `customers` | `id` (Int/BigInt per dialect) | `created_by_id`/`updated_by_id`→`users.id` | **partial unique index** `uq_customers_active_normalized_name` on `normalized_name` **where `is_active`** (Postgres/SQLite partial index) | this partial-unique pattern means two *inactive* (archived) customers **can** share a `normalized_name` — intentional (archiving frees the name for reuse) but worth knowing when auditing dedup/search logic |
| `ProjectContractor` | `project_contractors` | `id` | `created_by_id`/`updated_by_id`→`users.id` | same partial-unique-when-active pattern as `Customer` | `is_active` + `archived_at` — a third naming variant of the same concept, see §2 |
| `ProjectContractorAssignment` | `project_contractor_assignments` | `id` | `project_id`→`projects.id` (**`RESTRICT`**), `contractor_id`→`project_contractors.id` (**`RESTRICT`**) | partial unique index on `(project_id, contractor_id, role)` **where `status != 'ENDED'`** — this is the DB-level enforcement of "one active assignment per project/contractor/role", a real constraint, not just an app-level check | `RESTRICT` on both FKs means a `Project` or `ProjectContractor` cannot be hard-deleted while any assignment references it — consistent with neither model supporting hard delete from the UI in the first place |
| `ProjectUpdate` | `project_updates` | `id` | `project_id`→`projects.id` (`RESTRICT`), `contractor_assignment_id`→...`.id` (`RESTRICT`, nullable) | `CheckConstraint` on `update_type` | **`deleted_at` declared manually** (`project_update.py:26`), not via `SoftDeleteMixin` — functionally identical column but stylistically inconsistent, see §2 |
| `SystemSetting` | `system_settings` | `key` (String, **not a surrogate ID**) | `brand_logo_storage_object_id`→`storage_objects.id` | — | primary key is the setting name itself — a singleton-per-key table, no soft-delete (correct for this shape) |
| `ProjectDocumentFolder` | `project_document_folders` | `id` (DOCUMENT_ID) | `project_id`→`projects.id` (`CASCADE`, **nullable** — supports non-project "custom root" folders), `parent_id`→**self** (`RESTRICT`) | partial unique `(project_id)` where `is_root AND deleted_at IS NULL` | **self-referential `parent_id` with `RESTRICT`** (not `SET NULL`/`CASCADE`) — a folder with children cannot be deleted without first handling its children, a real DB-level safety backstop against orphaning; no cycle-prevention constraint either (same class of risk as `CompanyDepartment`/`PartnerRelationship`, though folders are created through the app's own folder-creation flow, not a free-form parent reassignment, which narrows but does not eliminate the risk — `move_folder`-shaped operations, out of scope, would need to check this) |
| `ProjectDocumentFile` | `project_document_files` | `id` | `folder_id`→...`.id` (`RESTRICT`), `storage_object_id`→`storage_objects.id` (**unique**, no `ondelete`) | `UniqueConstraint(storage_object_id)` — **a `StorageObject` can back at most one `ProjectDocumentFile`** | `is_active` + manually-declared `deleted_at`, see §2 |
| `ProjectDocumentFolderPermission` | `project_document_folder_permissions` | `id` | `folder_id`→...`.id` (`CASCADE`), `user_id`→`users.id` (`CASCADE`), `role_id`→`roles.id` (`CASCADE`) | `CheckConstraint` XOR: exactly one of `user_id`/`role_id` set; `UniqueConstraint(folder_id, user_id)` and `(folder_id, role_id)` separately | XOR constraint is a genuinely good DB-level guard against a malformed ACL row that names neither or both a user and a role |
| `CompanyMediaAlbum` | `company_media_albums` | `id` | `created_by_id`/`updated_by_id`→`users.id` | — | `cover_media_id` has **no FK constraint at all** (plain `db.Column(DOCUMENT_ID, nullable=True)`, `company_media.py:13`) — referential integrity for "which file is the cover" is enforced **only** by the `before_flush` event listener below (application-level, not schema-level) |
| `CompanyMediaFile` | `company_media_files` | `id` | `album_id`→...`.id` (`RESTRICT`), `storage_object_id`→`storage_objects.id` (**unique**) | `UniqueConstraint(storage_object_id)` | same 1:1 storage-object pattern as `ProjectDocumentFile`; `is_active` + manually-declared `deleted_at` |
| `CompanyMediaAlbumPermission` | `company_media_album_permissions` | `id` | `album_id`→...`.id` (`CASCADE`), `user_id`/`role_id`→...`.id` (`CASCADE`) | same XOR + double-unique pattern as the document-folder permission table | — |
| `StorageDerivative` | `storage_derivatives` | `id` (STORAGE_ID) | `storage_object_id`→`storage_objects.id` (no `ondelete`), `created_by_job_id`→`media_processing_jobs.id` (nullable) | `UniqueConstraint(bucket, object_key)`, `CheckConstraint` on `derivative_type` | `SoftDeleteMixin` present |
| `MediaProcessingJob` | `media_processing_jobs` | `id` | `storage_object_id`→`storage_objects.id` (no `ondelete`) | `UniqueConstraint(storage_object_id, job_type)`, `CheckConstraint` on `job_type`/`status` | no soft-delete; `attempts`/`max_attempts` are plain integers, not enum-constrained |
| `BulkDownloadJob` | `bulk_download_jobs` | `id` | `requested_by_id`→`users.id` | `CheckConstraint` on `module`/`status` | `requested_file_ids` is a `db.JSON` column (no FK integrity to the referenced files at all — the file IDs inside are opaque to the schema; whatever validates them does so in application code, out of this scope) |

**Two global SQLAlchemy `before_flush` event listeners exist** (both found
in this scope, both cross-object consistency guards, neither soft-delete-
related):
- `app/models/project_document.py:91-99`,
  `validate_project_document_file_folder` — raises `ValueError` if a
  `ProjectDocumentFile.project_id` disagrees with its `folder.project_id`.
- `app/models/company_media.py:62-68`, `validate_company_media_cover` —
  raises `ValueError` if `CompanyMediaAlbum.cover_media_id` points to a file
  belonging to a different album (this is also the *only* integrity check
  for `cover_media_id` at all, since that column carries no FK constraint —
  see the `CompanyMediaAlbum` row above).

---

## 2. Soft-delete / timestamp mixins — coverage and the multi-convention risk

`app/models/mixins.py`, in full:
```python
class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now(), onupdate=db.func.now())

class CreatedAtMixin:
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

class SoftDeleteMixin:
    deleted_at = db.Column(db.DateTime, nullable=True)
```

**Finding — no single soft-delete convention exists; this pass counted at
least six distinct "is this row gone/inactive" shapes across the 39
models**, and there is **no SQLAlchemy-level mechanism (no
`with_loader_criteria`, no global query filter, no custom `Query` class)
anywhere in this scope that automatically excludes any of them** — every
query, in every unit's own file, is 100% responsible for applying the
*correct* filter for *that specific model's* convention. This is exactly
the "forgotten filter = data leak" class of bug the instruction asked about,
and the model layer itself is where the inconsistency originates:

1. **`SoftDeleteMixin`'s `deleted_at` alone, nothing else**:
   `DailyReportSection`, `ReportAttachment`, `StorageDerivative`.
2. **`SoftDeleteMixin`'s `deleted_at` PLUS a separate `is_active` boolean,
   both present on the same row**: `User`, `ReportCategory`, `Company`,
   `Partner`, `PartnerRelationship`. **These two flags are not linked by any
   constraint or trigger** — nothing stops `deleted_at` being set while
   `is_active` stays `True`, or vice versa; a query that checks only one of
   the two could disagree with a query that checks the other.
3. **`is_active` alone, no `deleted_at`, no mixin**: `ProjectUser`,
   `CompanyDepartment`, `PartnerFieldDefinition`, `PartnerFieldCollection`.
4. **`is_active` + `archived_at`, no `SoftDeleteMixin`**: `Customer`,
   `ProjectContractor` — a *fourth* naming variant of #2's shape (different
   column name, same idea, same lack of linkage between the two columns).
5. **Manually re-declared `deleted_at` (not via the mixin) + `is_active`,
   both present**: `ProjectDocumentFolder`, `ProjectDocumentFile`,
   `CompanyMediaAlbum`, `CompanyMediaFile` — functionally identical to #2
   but the column was hand-written instead of inherited, meaning a future
   refactor of `SoftDeleteMixin` (e.g. adding an index) would silently miss
   these four models.
6. **Manually re-declared `deleted_at` alone, no `is_active`**:
   `ProjectUpdate` (`project_update.py:26`).
7. **Two independent "deleted" signals on the very same column set**:
   `StorageObject` carries `SoftDeleteMixin`'s `deleted_at` **and** an
   `upload_status` enum whose allowed values include the literal string
   `'deleted'` (`storage.py:12`, `CheckConstraint`). A query filtering only
   on `deleted_at IS NULL` could still return a row whose `upload_status ==
   'deleted'`, and vice versa — this is the single clearest concrete
   instance of the risk class asked about, on the model that backs *every*
   uploaded file in the entire application.
8. **No soft-delete concept at all (hard delete only)**: `RolePermission`,
   `PartnerFieldCollectionItem`, `PartnerFieldValue`,
   `ProjectDocumentFolderPermission`, `CompanyMediaAlbumPermission`,
   `DownloadEvent`, `Role`, `Permission`, `SystemSetting`,
   `UploadBatch`/`UploadBatchItem`/`UploadSelectionSession`/
   `MediaProcessingJob`/`BulkDownloadJob` (these last five are
   operational/job-tracking tables where hard delete or pure status-driven
   lifecycle is the correct design, not a gap).
9. **`Project` itself layers a third concept on top of #2's shape**: it has
   `SoftDeleteMixin`'s `deleted_at` **and** a `status` column whose
   `CheckConstraint`-allowed values include `'archived'`
   (`project.py:9-13`). "Deleted" and "archived" read as different concepts
   in the product (`AGENTS.md`'s `ProjectStatus` enum has always
   distinguished paused/completed/archived as active lifecycle states, not
   deletion), so this specific case is likely intentional rather than
   accidental — but it means a query must know to check `deleted_at IS
   NULL` for "not deleted" and separately decide whether `status ==
   'archived'` should also be excluded from a given view, and nothing
   enforces that a caller does both correctly.

**Every place the filter could be forgotten, per this pass's model-only
reading** (query call sites themselves are out of this unit's scope — this
is the risk surface each downstream unit must check against its own
routes/services):

- Any query against `StorageObject` that checks `deleted_at` but not
  `upload_status`, or vice versa (highest-impact, since every file-serving
  path in the app reads this table).
- Any query against `User`, `ReportCategory`, `Company`, `Partner`, or
  `PartnerRelationship` that checks `is_active` but not `deleted_at`, or
  vice versa.
- Any query against `Customer`/`ProjectContractor` that checks `is_active`
  but not `archived_at`, or vice versa — plus the partial-unique-index
  behavior noted in §1 (two archived rows can share a name; a naive
  `normalized_name` lookup that doesn't also filter `is_active` could match
  the wrong one of several archived duplicates).
- Any query against `ProjectDocumentFolder`/`ProjectDocumentFile`/
  `CompanyMediaAlbum`/`CompanyMediaFile` that checks `is_active` but not the
  manually-declared `deleted_at`, or vice versa.
- Any query against `Project` that checks `deleted_at` but treats
  `status == 'archived'` rows as still fully "active" (or the reverse).

---

## 3. Tenant / project scoping at the data layer

**There is none, at the model or query-construction layer.** Confirmed by
reading every model file in full: no model overrides `Model.query`, no
custom `BaseQuery` class exists anywhere in this scope, no
`with_loader_criteria` (SQLAlchemy 1.4+'s mechanism for exactly this kind of
automatic global filter) is registered anywhere, and no mixin analogous to
`TimestampMixin`/`SoftDeleteMixin` exists for "always filter by accessible
project IDs." Every model that has a `project_id` column
(`ReportCategory`, `DailyReport`, `PersistentIssue`,
`ProjectContractorAssignment`, `ProjectUpdate`, `ProjectDocumentFolder`,
`ProjectDocumentFile` via its folder) is a **plain column with a foreign
key**, nothing more — scoping to "projects this user may see" is **entirely
the calling code's responsibility**, every single time, in every route and
service file across every Batch 1+ unit. `app/project_memberships.py`'s
`accessible_project_ids()` (A1 scope, cited not re-derived here) exists as a
*helper* a caller can choose to use — it is not wired into the ORM itself
in any way that would make forgetting it impossible.

**Consequence for Batch 1+ IDOR risk**: this means the "three-layer
authorization model" (module gate → RBAC → per-project capability,
`FOUNDATION-A1.md` §4) is the *entire* defense for tenant/project isolation
— there is no second, independent, data-layer backstop. A route that
correctly checks `can_view_report(user, report)` before rendering a report
is safe; a route that forgets to, or that loads a *related* object without
re-checking (a classic confused-deputy pattern — e.g. loading a
`DailyReportSection` by ID and trusting it belongs to a report the caller
already validated, without re-verifying the section's `daily_report_id`
matches), has **zero model-level safety net** to fall back on. Every
Batch 1+ unit should treat every `project_id`-bearing model as "IDOR until
proven otherwise by reading the actual query," not assume the schema
protects anything.

---

## 4. Role predicates — `is_project_admin`, `is_viewer_admin`, `User` role handling

**Correction to `FOUNDATION-A1.md`**: that document stated these predicates
"are not defined in any file in this unit's scope" and flagged their
resolution as A2's responsibility. Investigating for this pass found they
are in fact defined in `app/project_memberships.py:70-75` — a file A1 *did*
read, just not far enough down to reach these two functions (A1's own
quotes from that file stopped at line 57 and resumed at line 78). This is
noted here as a correction, not left as an open gap, since the actual
content is available and worth resolving now rather than deferring further.
Quoted in full:

```python
def is_project_admin(user):
    return bool(user and getattr(user, "is_authenticated", False) and user.is_active and user.role_code in ADMIN_ROLE_CODES)

def is_viewer_admin(user):
    return bool(user and getattr(user, "is_authenticated", False) and user.is_active and user.role_code == VIEWER_ADMIN_CODE)
```

where `ADMIN_ROLE_CODES = {UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value}`
and `VIEWER_ADMIN_CODE = UserRole.VIEWER_ADMIN.value`
(`app/project_memberships.py`, module-level constants). **CONFIRMED: both
predicates do exactly what their names suggest** — `is_project_admin` is
true only for `SUPER_ADMIN`/`ADMIN`, `is_viewer_admin` is true only for
`VIEWER_ADMIN`, both require `is_authenticated` and `is_active`, and both
read `user.role_code`, which (per `User.role_code`, `app/models/user.py:77-79`,
quoted in full: `return self.role.code if self.role is not None else None`)
is derived from the **canonical `role_id` foreign-key relationship**, never
from the `legacy_role`/`role` mirror column (`app/models/user.py:20`,
comment: "never authorization input" — confirmed true by this property's
implementation, which doesn't reference `legacy_role` at all).

`User.has_role(code)` (`user.py:81-82`) is a thin wrapper:
`self.role_code == code`. `User.can(code)` (`user.py:84-87`) delegates to
`app.permissions.services.user_has_permission` (A1 scope, already covered
there). No other role-handling logic exists in `app/models/user.py` beyond
these three methods and `check_password`.

**GUARANTEES/NOT GUARANTEED in this document are updated to reflect this
resolution** (see end of file) — `FOUNDATION-A1.md`'s own NOT GUARANTEED
list still stands as written (it was correct to flag this as unverified at
the time), this document is what closes it.

---

## 5. `app/audit.py` in full

```python
def log_audit(action, entity_type, entity_id=None, old_values=None, new_values=None):
    log = AuditLog(
        actor_user_id=_actor_user_id(), action=action, entity_type=entity_type, entity_id=entity_id,
        old_values_json=old_values, new_values_json=new_values,
        ip_address=_ip_address(), user_agent=_user_agent(),
    )
    _add_with_sqlite_id(log)
    return log

def _actor_user_id():
    if not has_request_context() or not current_user.is_authenticated:
        return None
    return current_user.id

def _ip_address():
    if not has_request_context():
        return None
    return request.headers.get("X-Forwarded-For", request.remote_addr)

def _user_agent():
    if not has_request_context():
        return None
    return request.headers.get("User-Agent")

def _add_with_sqlite_id(instance):
    if getattr(instance, "id", None) is None and db.engine.name == "sqlite":
        max_id = db.session.query(func.max(type(instance).id)).scalar() or 0
        instance.id = max_id + 1
    db.session.add(instance)
```

**PRE-001 (`_ip_address` trusting raw `X-Forwarded-For`) is confirmed
already and not re-derived here.** Full set of fields an attacker (any
authenticated or even unauthenticated-but-request-issuing client) can
influence in a resulting `AuditLog` row, reasoned from this function alone:

- **`ip_address`** — fully attacker-controlled (PRE-001), any string, up to
  whatever length the `X-Forwarded-For` header allows (column is
  `db.String(100)`, `audit_log.py:18` — a value longer than 100 chars would
  raise a DB-level error on insert for Postgres's `VARCHAR(100)`, which is a
  potential unhandled-exception path if a caller doesn't truncate before
  passing it in — not verified whether any caller does, out of scope; the
  function itself performs no length check).
- **`user_agent`** — fully attacker-controlled, raw `User-Agent` header
  value, stored as `db.Text` (unbounded) with **no sanitization** — stored
  verbatim. Since this is a DB column, not directly rendered as HTML
  anywhere in this scope, it is not by itself an XSS vector *here*, but
  **any admin UI that later displays `AuditLog.user_agent` (or
  `ip_address`) without escaping would be** — flagged for whichever unit
  renders audit-log rows in a template (not found in this scope's files;
  cross-reference unit 14, Template output safety, if such a view exists).
- **`old_values_json`/`new_values_json`** — attacker influence is
  *indirect and caller-dependent*: the function accepts whatever the
  calling code passes. The one call site available to inspect in this pass
  (`app/auth/routes.py:35`, A1 scope, already read there) passes
  `new_values={"login": login_value}` where `login_value` is the raw,
  attacker-supplied login-form field (bounded to 255 chars by
  `LoginForm`'s `Length(max=255)` validator, but otherwise unsanitized free
  text) — so at least one real code path does put attacker-controlled free
  text into this JSON column. Other call sites (out of this pass's file
  scope) were not surveyed.
- **`action`/`entity_type`/`entity_id`** — chosen by the calling code as
  fixed string literals / real object IDs in every call site seen so far;
  no evidence of attacker control over these three fields in this pass.

**Append-only or mutable?** The `AuditLog` model itself
(`app/models/audit_log.py`) defines no update-oriented method, no
soft-delete, and `log_audit()` only ever constructs and `db.session.add()`s
a new row — nothing in this scope calls `.update()`/`db.session.merge()`
against an existing `AuditLog` row. **However, nothing at the schema level
enforces immutability either** — no DB trigger, no `REVOKE UPDATE`
grant, no read-only table configuration was found in the migrations
touching `audit_logs` (the table is created once in the initial schema
migration and never altered again in the 29-migration chain, confirmed by
grepping every migration file for `audit_logs` — it appears only in
`20260708_0001_initial_schema.py`). **Conclusion: append-only by
convention and by the absence of any call site that mutates a row in this
codebase, not by any enforced guarantee** — a future code change (or a
direct DB `UPDATE` by anyone with database access) could alter historical
audit rows undetected, since there's no checksum/hash-chain or
write-once database permission in place.

**Does any security-relevant action write no audit entry?** Within the
files actually read across this pass and `FOUNDATION-A1.md`'s pass
(`app/auth/routes.py`, fully read in A1): **`login()` logs only the failed
case** (`log_audit("auth.login_failed", ...)`, line 35) — a *successful*
login writes no audit row at all. **`logout()` and `change_password()` call
`log_audit` zero times** — neither a successful nor failed password change,
nor a logout event, is recorded anywhere in the audit trail, as far as
`app/auth/routes.py`'s own code goes. This is a real, concrete gap in
security-event coverage (a password change is exactly the kind of thing an
incident investigation would want a timestamped record of) — but this
pass's scope cannot rule out that some *other* file calls `log_audit` for
these events via a signal/hook this pass didn't see (e.g. a
`flask_login`-signal-based listener) — **did not find one in any file read
across A1+A2**, but did not exhaustively search every file in the repo for
`log_audit`/`audit(` call sites either (that would exceed both units'
scopes). Recommend whichever unit ends up owning `app/auth/routes.py`
(already covered in A1) or a later cross-cutting pass confirm this with a
full-repo grep for `log_audit\(` before treating it as certain.

---

## 6. Migration integrity

**Chain shape**: linear, no branches. Walked all 29 `revision`/
`down_revision` pairs (one file, `20260720_0011_add_media_processing_foundation.py`,
uses a dense semicolon-joined one-line style that a naive `grep "^revision
= "` misses — corrected for by reading the file directly) — the chain is a
single unbroken sequence from `20260708_0001` (`down_revision = None`) to
`c4d2e980f617` (the current head, matching `README.md`'s reference to this
file), 29 files, no merge points, no divergent heads. **Every one of the 29
files defines a `def downgrade` function** (confirmed by grep across all
files — zero files with a missing downgrade).

**Reversibility, spot-checked on the four most consequential migrations**
(chosen for being named as destructive or flagged by semgrep, not a random
sample):

- **`20260722_0014_three_layer_authorization.py`** (the semgrep
  `avoid-sqlalchemy-text` source, §"tool leads" below) — `upgrade()`
  reassigns legacy `PROJECT_MANAGER`/`REPORTER` users to a new
  `PROJECT_STAFF` role and renames the old role rows with a
  `'[Deprecated] '` prefix, via raw SQL built from **hardcoded,
  module-level constant tuples** (`FLAGS`, lines 14-20, and an inline tuple
  at lines 48-51) — **confirmed no interpolated value in this file's SQL
  can come from outside the operator running `flask db upgrade`; nothing
  here is reachable from any HTTP request.** `downgrade()` (lines 63-73)
  reverses only the **schema** changes (drops the added columns, renames
  `project_role_code` back to `role_in_project`, restores the old
  `ck_users_role` check constraint) — it does **not** reverse the **data**
  changes (`PROJECT_STAFF` reassignments, the `'[Deprecated] '` role-name
  rewrite). Running `downgrade` after `upgrade` restores the old schema
  shape but leaves users/roles data in the post-migration state — **this
  migration's downgrade is not a true rollback once real data has passed
  through it**, which is a normal, common (if under-documented) asymmetry
  for migrations that touch data, not a bug, but worth flagging explicitly
  since "is every migration reversible" was asked directly.
- **`20260723_0021_partner_reports_s3_only.py`** — `upgrade()` guards
  against data loss with a pre-flight query (`SELECT count(*) FROM
  report_attachments WHERE deleted_at IS NULL AND storage_object_id IS
  NULL`) and **raises `RuntimeError` with an operator remediation command**
  if any active attachment still lacks a storage object, before dropping
  `file_path`/`stored_filename` and adding the DB-level check constraint
  mentioned in §1. `downgrade()` re-adds both columns as nullable — this
  correctly restores the *schema* but the dropped columns' **historical
  values for rows that existed before the drop are permanently gone**
  (this is inherent to any `drop_column`, not a bug in this specific
  migration — the guard exists precisely to make sure no *active* row's
  data was actually needed at drop-time).
- **`20260724_0023_daily_reports_hard_delete.py`** — same pattern: guards
  with `SELECT COUNT(*) FROM daily_reports WHERE deleted_at IS NOT NULL`,
  raises `RuntimeError` pointing the operator at
  `flask dev-purge-deleted-reports --apply --confirm "PURGE DELETED
  REPORTS"` if any soft-deleted reports still exist, then drops
  `deleted_at` from `daily_reports`. **This is the migration that explains
  why `DailyReport` (§1) has no soft-delete column today** — it used to,
  and this migration deliberately removed it, with a data-loss guard.
  `downgrade()` re-adds `deleted_at` as nullable. **Consequence for unit
  3a**: since this table has no soft-delete mechanism anymore, whatever the
  `reports.delete` route (out of this pass's scope) actually does to a
  `DailyReport` today must be either a real hard `DELETE`, or some other
  mechanism not visible in the model — this is a direct, concrete question
  for unit 3a to resolve, not a gap in this document.
- **`20260720_0011_add_media_processing_foundation.py`** — pure
  `create_table`/`create_index` in `upgrade()`, symmetric `drop_table` in
  `downgrade()` — fully reversible, no data-loss risk (no pre-existing data
  to lose in new tables).

**Two other `drop_column`-shaped migrations exist that were *not*
individually re-read in full this pass** (found across 26 files matching
`drop_column|drop_table` in `upgrade()` **or** `downgrade()` — most of
those 26 hits are inside `downgrade()`, which is expected/safe; this pass
did not verify each one individually) — flag for whichever unit needs full
migration confidence before Phase 11 to do a complete pass rather than rely
on this document's four-migration sample.

**Does the schema the migrations produce match what the models declare?**
One confirmed mismatch, already noted in §1:
`ck_report_attachments_active_storage_object` (created in migration
`0021`) is a real, enforced DB constraint that has **no corresponding
declaration in `app/models/daily_report.py`**'s `ReportAttachment.__table_args__`
— the model is silent about it. This isn't a functional bug (the
constraint still applies at the DB level regardless of whether the ORM
model declares it), but it means **reading the model file alone
understates what the database actually enforces** — anyone reasoning about
`ReportAttachment`'s invariants from the model file alone would miss this
constraint entirely. Did not exhaustively diff every migration's DDL
against every model's declared columns/constraints beyond this one
instance and the four migrations read in full — a full schema-vs-model diff
(e.g. via `alembic check` or comparing `Model.__table__` reflection against
a real migrated database) was not performed and would be needed for
complete confidence.

---

## 7. Money, dates, timezones

- **No `db.Float` column exists anywhere in `app/models/`** (confirmed by
  grep across all 19 files) — every quantity that could be money/size/
  duration uses an exact type: `db.BigInteger` for byte counts
  (`file_size`, `total_size_bytes`, etc.), `db.Numeric(12,3)` for
  `duration_seconds`, `db.Numeric(18,4)` for `PartnerFieldValue.value_number`.
  **This codebase has no monetary columns at all** in this schema (matches
  `ARCHITECTURE.md`'s earlier observation that there is no payment/billing
  model) — so the "float used for a quantity that should be exact" concern
  doesn't have a live instance to point at, but the type discipline itself
  is confirmed sound for the quantities that do exist.
- **Every `db.DateTime` column in this entire schema is naive** — zero uses
  of `timezone=True` anywhere in `app/models/` (confirmed by grep). All
  `TimestampMixin`/`CreatedAtMixin` timestamps default via `db.func.now()`
  (→ `CURRENT_TIMESTAMP` at the DB level). **This means consistency depends
  entirely on the database server's own configured timezone plus
  applicationcode discipline never mixing local-time and UTC values into
  the same naive column** — nothing in the schema itself can catch a
  mistake here (a naive datetime silently accepts any wall-clock value
  regardless of which zone it was meant to represent).
- **`app/date_utils.py`, in full, read in this pass**: `APP_TIMEZONE =
  ZoneInfo("Asia/Ho_Chi_Minh")` (`date_utils.py:8`), used only by
  `local_today()` (`date_utils.py:24-26`, returns a `date`, not a
  `datetime` — no timezone-attachment ambiguity for that specific value
  since `Date` columns have no time-of-day component at all).
  `format_vn_date`/`parse_iso_date` are pure string↔`date` converters, not
  timezone-aware in any way that could introduce naive/aware mixing. **This
  file itself introduces no naive-datetime risk** — the risk identified
  above is purely in the model layer's timestamp columns, not in this
  helper file.
- **Practical implication for later units**: any comparison between a
  `Date`-typed business value (`report_date`, `update_date`, `opened_date`,
  etc. — all correctly typed `db.Date`, no time-of-day/timezone ambiguity)
  and a `DateTime`-typed audit column (`created_at`, `updated_at`,
  `completed_at`, etc. — all naive) must be done carefully; this pass found
  no code in its own scope that does such a comparison incorrectly (no
  comparison logic lives in the model files at all), but flags it as a
  pattern for Batch 1+ units (especially 3a/dashboard/9) to watch for when
  they reach service-layer date arithmetic.

---

## GUARANTEES

Module auditors in Batch 1+ may assume, without re-deriving:

- Every `ProjectUser` capability flag defaults to `False` at the column
  level (`nullable=False, default=False, server_default="false"`,
  `project.py:99-115`) — a newly created membership row grants nothing
  until the granting code explicitly sets a flag to `True`.
- `is_project_admin`/`is_viewer_admin` do exactly what their names imply
  (§4) — this closes the gap `FOUNDATION-A1.md` flagged as open.
- `User.role_code` (and therefore both admin predicates and `User.can()`)
  is derived solely from the canonical `role_id` relationship, never from
  the legacy `role`/`legacy_role` mirror column.
- `PartnerFieldValue` genuinely snapshots the field definition's shape at
  write time (`field_label_snapshot`/`field_key_snapshot`/
  `field_type_snapshot`/`group_name_snapshot`) — a later rename/reorder/
  retirement of a `PartnerFieldDefinition` cannot silently reinterpret
  historical values, confirmed at the schema level.
- The `ProjectDocumentFile`↔`folder` project match and the
  `CompanyMediaAlbum`↔`cover_media_id` album match are enforced by
  SQLAlchemy `before_flush` listeners that run on every session flush,
  not just at the route layer — these two specific invariants cannot be
  violated by ORM writes even if a service function forgets to check them
  itself.
- `ProjectDocumentFolderPermission`/`CompanyMediaAlbumPermission` both
  enforce, at the DB level, that exactly one of `user_id`/`role_id` is set
  (XOR check constraint) — a malformed "grants to nobody and everybody"
  ACL row is impossible.
- `ProjectContractorAssignment`'s partial unique index genuinely prevents
  two simultaneously-`ACTIVE`-or-non-`ENDED` assignments for the same
  project/contractor/role — this is a real DB constraint, not merely an
  app-level check.
- No monetary value or size/duration quantity anywhere in this schema uses
  a floating-point column.

## NOT GUARANTEED — every unit must check these per-model/per-query itself

- **There is no data-layer tenant/project scoping anywhere** (§3) — every
  query against every `project_id`-bearing model must be individually
  confirmed to filter correctly; the schema provides zero backstop.
- **At least six different soft-delete/inactive conventions coexist**
  (§2), several with two independent flags on the same row that can
  disagree (`StorageObject` most acutely). No unit should assume a single
  `is_active`/`deleted_at` check is sufficient for any given model without
  first confirming, from this document's §2 table, which convention(s)
  that specific model actually uses.
- **`DailyReport` has no soft-delete mechanism of any kind** — confirmed
  deliberate (migration `20260724_0023`), but this means whatever
  `reports.delete` does today is either a genuine hard delete or something
  not visible at the model layer; unit 3a must resolve this specifically,
  it is not assumed safe or unsafe here.
- **`CompanyDepartment.parent_department_id` and
  `PartnerRelationship.parent_relationship_id` are self-referential with no
  DB-level cycle prevention** — unit 6b's cycle/depth deliverable
  (`partner_relations/routes.py:145`) cannot rely on the schema to have
  ruled out a cycle; it must be checked in the query/service logic that
  builds the tree.
- **`CompanyMediaAlbum.cover_media_id` has no foreign-key constraint at
  all** — its only integrity guarantee is the `before_flush` listener
  (which does run on every flush, so this is close to a real guarantee, but
  it is application-code-enforced, not schema-enforced, and a raw SQL
  write bypassing the ORM session would not trigger it).
- **The audit trail has real, confirmed gaps**: successful login, logout,
  and password-change events write no `AuditLog` row at all, as far as
  `app/auth/routes.py`'s code goes (§5) — do not assume any authentication
  lifecycle event beyond a *failed* login is recorded anywhere.
- **`AuditLog` is append-only by convention and absence of counter-evidence,
  not by any enforced database or application guarantee** — no trigger, no
  restricted DB permission, no hash-chaining exists to detect or prevent a
  later mutation of a historical row.
- **`user_agent` and `ip_address` on `AuditLog` are attacker-controlled,
  unsanitized free text** (§5, extending PRE-001) — any future admin UI
  that renders these values must escape them; this pass found no such UI
  in scope, but did not exhaustively search for one either.
- **Migration reversibility was verified in depth for only 4 of 29
  files** — the chain is confirmed linear and every file has *a*
  `downgrade()`, but this does not mean every `downgrade()` is a complete,
  data-preserving rollback (the one migration checked in most depth for
  this, `20260722_0014`, explicitly is not, for its data-touching parts).
  Treat "downgrade exists" as "a downgrade path exists," not as "downgrade
  restores prior state exactly."
- **This pass did not perform a full schema-vs-model DDL diff** — one
  confirmed model/migration divergence exists
  (`ck_report_attachments_active_storage_object`, §6); others may exist
  undetected.
