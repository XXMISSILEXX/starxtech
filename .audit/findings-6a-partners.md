# Findings — Unit 6A: Partners core

## Summary

- Both registered primary blueprints are behind the global login hook (`app/__init__.py:155-167`) and an independent blueprint module gate: `partners` at `app/partners/routes.py:34-38` and `partner_companies` at `app/partner_companies/routes.py:15-18`. The gate is `current_user.can("modules.partners.access")` (`app/auth/permissions.py:68-70`).
- This is a module-wide PII system, not a project- or object-scoped one. `can_view_partner`, `can_edit_partner`, and `can_delete_partner` ignore their `partner` argument and re-check global RBAC only (`app/auth/permissions.py:118-139`). Every partner/company holder of the corresponding view permission can therefore see the module’s names, contact details, addresses, notes, field values, and display images by design.
- Archive/deactivate parity is intact for both Partners and Companies: each `/deactivate` handler delegates directly to the protected `/archive` handler. Restore requires the separate `.restore` permission. The different concern is that Company and Department edit routes can change lifecycle state without the dedicated restore/delete permission.
- Partner photos are transformed to WebP and bound to a `StorageObject`; preview authorization is checked before presigning. The GET preview route nevertheless returns the resulting bearer URL in a redirect location.
- Files read: 17 primary files (all six files in `app/partners/` and `app/partner_companies/`, `app/partner_photos.py`, and the 10 matching templates), plus direct call-chain support including registration, global hooks, permission helpers, models, audit, display-image, and storage state code. Files skipped: none in the assigned primary scope. The excluded `claude-partial-audit-backup/` directory was not read.

## Findings

### PARTNER-001 — Company editor can alter an archived company’s active flag without restore authority

- **Severity:** Medium
- **Confidence:** High
- **CWE:** CWE-863
- **Location:** `app/partner_companies/routes.py:186-192, 227-244`
- **Reachability:** Authenticated user who passes the Partners module gate and has `partner_companies.edit`; no `partner_companies.restore` or `partner_companies.delete` is required. The normal UI suppresses editing archived companies, but the POST route remains directly reachable.
- **Evidence:**
  ```python
  @bp.route("/<int:company_id>/edit", methods=["GET", "POST"])
  @permission_required("partner_companies.edit")
  def edit(company_id):
      company = _company_or_404(company_id)
      if request.method == "POST":
          return _save_company(company)
  ```
  `app/partner_companies/routes.py:186-191`

  Unlike the department mutations, this path does not call `_require_active_company_for_mutation`. `_save_company` accepts the posted state and commits it:
  ```python
  company.is_active = request.form.get("is_active", "on") == "on"
  audit("partner_company.create" if is_new else "partner_company.update", "Company", company.id, old_values, _company_snapshot(company))
  db.session.commit()
  ```
  `app/partner_companies/routes.py:242-244`

  The dedicated restore path instead requires the distinct permission and clears both lifecycle fields:
  ```python
  @permission_required("partner_companies.restore")
  def restore(company_id):
      company = archived_record_query(Company).filter(Company.id == company_id).first_or_404()
      company.is_active = True
      company.deleted_at = None
  ```
  `app/partner_companies/routes.py:214-220`
- **Exploit:** Archive a company, then submit a direct POST to `/partner-companies/<id>/edit` with a valid CSRF token and `is_active=on`. The handler accepts the archived object, commits `is_active=True`, and leaves `deleted_at` unchanged. A user granted only edit thus alters lifecycle state that the dedicated restore endpoint reserves for `.restore`.
- **Impact:** A company can enter the inconsistent `is_active=True, deleted_at!=NULL` state. Current active-query helpers require both flags, but other code can observe a misleading active flag; the archived record is also changed despite the product/UI statement that it is view-only. The audit snapshot omits `deleted_at`, making the two-flag state harder to reconstruct from this event.
- **Effort:** S

### PARTNER-002 — Department editor can reactivate a deactivated department without delete authority

- **Severity:** Medium
- **Confidence:** High
- **CWE:** CWE-863
- **Location:** `app/partner_companies/routes.py:161-169, 172-181, 305-347`
- **Reachability:** Authenticated Partners-module user with `partner_companies.edit` can directly POST to a deactivated department’s edit URL. The UI does not expose that link for inactive departments, but the server-side lookup is scoped only by company and ID, not active state.
- **Evidence:**
  ```python
  @bp.route("/<int:company_id>/departments/<int:department_id>/edit", methods=["GET", "POST"])
  @permission_required("partner_companies.edit")
  def departments_edit(company_id, department_id):
      company = _company_or_404(company_id)
      department = _department_or_404(company.id, department_id)
      if request.method == "POST":
          _require_active_company_for_mutation(company)
          return _save_department(company, department)
  ```
  `app/partner_companies/routes.py:161-168`

  The edit save path controls the status from the request:
  ```python
  department.is_active = request.form.get("is_active", "on") == "on"
  audit("partner_department.create" if is_new else "partner_department.update", "CompanyDepartment", department.id, old_values, _department_snapshot(department))
  db.session.commit()
  ```
  `app/partner_companies/routes.py:344-347`

  Deactivation is a separate dangerous operation guarded by a stronger permission:
  ```python
  @bp.post("/<int:company_id>/departments/<int:department_id>/delete")
  @permission_required("partner_companies.delete")
  def departments_delete(company_id, department_id):
      ...
      department.is_active = False
  ```
  `app/partner_companies/routes.py:172-180`
- **Exploit:** A user with only `partner_companies.edit` submits the inactive department’s edit form directly with `is_active=on`. `_department_or_404` returns inactive rows, and `_save_department` commits the active flag without consulting `.delete` or a distinct restore permission.
- **Impact:** The user can reverse a lifecycle action that required `partner_companies.delete`, bypassing the intended permission separation. Because a department has no `deleted_at` field, this is an effective restoration, not merely a two-flag inconsistency.
- **Effort:** S

### PARTNER-003 — GET photo previews disclose a presigned bearer URL in redirect headers

- **Severity:** Low
- **Confidence:** High
- **CWE:** CWE-200
- **Location:** `app/partners/routes.py:204-210`; `app/partner_companies/routes.py:115-120`; `app/partner_photos.py:32-48`
- **Reachability:** Any authenticated user with the relevant global PII view permission can call the corresponding GET preview endpoint for any partner/company in the module-wide scope.
- **Evidence:**
  ```python
  @bp.get("/<int:partner_id>/photo/preview")
  @permission_required("partners.view")
  def photo_preview(partner_id):
      partner = _partner_or_404(partner_id)
      if not can_view_partner(partner): abort(403)
      from app.partner_photos import signed_preview
      return redirect(signed_preview(partner, kind="profile_photo", user=current_user)["url"])
  ```
  `app/partners/routes.py:204-210`

  The company equivalent has the same redirect construction at `app/partner_companies/routes.py:115-120`. `signed_preview` does perform a correct state check and creates the signed URL only after that:
  ```python
  if obj is None or obj.deleted_at is not None or obj.upload_status != "active":
      raise PartnerPhotoError("Chưa có ảnh để xem trước.")
  ...
  return create_presigned_download(obj, user=user, filename=obj.original_filename, variant="preview")
  ```
  `app/partner_photos.py:32-48`
- **Exploit:** An authorized viewer requests the GET preview endpoint. The application emits the temporary object-store capability in `Location`; software recording response headers, browser history, or intermediaries can retain/replay it until its TTL expires.
- **Impact:** Temporary access to a partner profile photo or company logo can escape the application’s normal route-level authorization audit trail. This is bounded because the caller already has module-wide view access and the URL is time-limited.
- **Effort:** S

### PARTNER-004 — Partner form accepts inactive definitions, duplicate rows, and arbitrary select values from a crafted POST

- **Severity:** Low
- **Confidence:** High
- **CWE:** CWE-20
- **Location:** `app/partners/services.py:109-115, 174-211`; `app/partners/routes.py:132-149, 213-234`
- **Reachability:** Authenticated Partners-module user with `partners.create` or `partners.edit`; valid CSRF protection still applies. The client can supply arbitrary `fields[n][field_definition_id]` values.
- **Evidence:**
  ```python
  definition_id = _optional_int(form.get(f"fields[{index}][field_definition_id]"))
  if not definition_id:
      continue
  definition = db.session.get(PartnerFieldDefinition, definition_id)
  if not definition:
      continue
  ...
  rows.append({
      "field_definition_id": definition.id,
      ...
  })
  ```
  `app/partners/services.py:185-210`

  There is no `definition.is_active` condition and no de-duplication by definition ID. The typed-value assignment also stores posted select values without comparing them with `definition.options_json`:
  ```python
  if field_type in {"text", "textarea", "url", "email", "phone", "select"}:
      value.value_text = str(raw_value or "").strip()
  ...
  elif field_type == "multi_select":
      value.value_json = [item.strip() for item in (raw_value or []) if item.strip()]
  ```
  `app/partners/services.py:294-312`

  The save operation clears the existing list and appends every accepted row:
  ```python
  partner.field_values[:] = []
  db.session.flush()
  for row in field_rows:
      value = PartnerFieldValue(partner_id=partner.id)
      _add_with_sqlite_id(value)
      _populate_field_value(value, row)
      partner.field_values.append(value)
  ```
  `app/partners/services.py:109-115`
- **Exploit:** Submit repeated field rows referencing the same valid definition, reference a definition deactivated by an administrator, or submit a `select`/`multi_select` value absent from its configured option list. The request creates multiple `PartnerFieldValue` records, recreates a value for an inactive definition, or stores an out-of-catalogue option even though the normal form only exposes active definitions and their configured options.
- **Impact:** Historical partner PII/custom data can be duplicated, inactive/stale field definitions can be reintroduced, and controlled-vocabulary data loses integrity, making later PII review/export ambiguous. No cross-partner replacement was found: values are always rebuilt on the route-selected `partner` object.
- **Effort:** S

### PARTNER-005 — Partner create/edit commits data before unhandled display-image failure

- **Severity:** Low
- **Confidence:** High
- **CWE:** CWE-703
- **Location:** `app/partners/routes.py:136-147, 220-232`; `app/display_images.py:36-83`
- **Reachability:** Authenticated user with `partners.create` or `partners.edit` submits a valid partner form with a photo whose name passes the extension allow-list but whose image processing or storage operation raises `DisplayImageError` or another unhandled exception.
- **Evidence:**
  ```python
  partner = save_partner(request.form)
  audit("partner.create", "Partner", partner.id, new_values=_partner_snapshot(partner))
  db.session.commit()
  if request.files.get("photo") and request.files["photo"].filename:
      from app.partner_photos import replace_photo
      replace_photo(partner, request.files["photo"], kind="profile_photo", user=current_user)
  except PartnerValidationError as exc:
      db.session.rollback()
  ```
  `app/partners/routes.py:138-145`

  The image implementation can raise its own exception after reading and decoding the upload:
  ```python
  if extension not in IMAGE_EXTENSIONS:
      raise DisplayImageError(...)
  ...
  except (UnidentifiedImageError, OSError, ValueError) as exc:
      raise DisplayImageError("Tệp tải lên không phải ảnh hợp lệ.") from exc
  ```
  `app/display_images.py:39-64`
- **Exploit:** Submit a valid partner create/edit request plus malformed bytes named, for example, `photo.jpg`. The partner fields and audit row commit first; the subsequent `DisplayImageError` is not a `PartnerValidationError`, so the route returns a generic failure after the mutation has already persisted.
- **Impact:** The caller receives a failure for an operation that actually created or changed PII, encouraging retries and duplicate records. The successful data mutation and failed image attachment are not atomically represented by the request result.
- **Effort:** M

## Explicitly checked and found clean

- Route registration and endpoint names are real: `partners` and `partner_companies` are registered at `app/__init__.py:131-132`; their blueprint names/prefixes are `partners`/`/partners` and `partner_companies`/`/partner-companies` (`app/partners/__init__.py:3`, `app/partner_companies/__init__.py:3`). App-level login runs before both blueprint hooks (`app/__init__.py:155-167`).
- All partner list, search, dashboard, detail, create, edit, archive/deactivate, restore, photo, and preview routes carry the corresponding route permission and the module gate. The lack of object ownership checks is deliberate module-wide visibility, not an untraced IDOR: the `can_*_partner` helpers are global RBAC checks (`app/auth/permissions.py:118-139`).
- Archive/deactivate parity: `partners.deactivate` calls `archive(partner_id)` (`app/partners/routes.py:253-256`), and `partner_companies.deactivate` calls `archive(company_id)` (`app/partner_companies/routes.py:208-211`). Both archive paths set `is_active=False` and `deleted_at=func.now()` (`partners/routes.py:245-246`, `partner_companies/routes.py:200-201`); restores use the respective dedicated `.restore` permissions.
- Archived partners are intentionally detail-viewable but not editable: detail uses `_partner_or_404` (`app/partners/routes.py:153-169`) while edit/photo/archive use `_active_partner_or_404` (`:172-188, 213-242`). Thus their field values, relationships displayed through company detail, and photo preview remain visible to a permitted module viewer, but mutations reject them.
- Partner/company photo target substitution is blocked by loading the route-selected partner/company before calling `replace_photo`; the image helper mutates that record’s attribute only (`app/partner_photos.py:18-29`, `app/display_images.py:79-83`). Old storage objects are marked with both `deleted_at` and `upload_status="deleted"` (`app/display_images.py:81-82, 86-90`); preview checks both state fields (`app/partner_photos.py:32-34`).
- Storage ownership/type is correctly bound for this integration: the display helper creates the object with `storage_module="partner-management"`, `mime_type="image/webp"`, and the uploader ID (`app/display_images.py:68-72`), normalizes images to WebP (`:47-60`), and uses generated keys through `build_display_image_key` (`:67`).
- Company/department client-supplied hierarchy IDs are server-checked. `_save_department` requires an existing, active parent in the same company and rejects self/descendant parenting (`app/partner_companies/routes.py:319-329`); child edit/delete scope the department by both URL company ID and department ID (`:274-278`).
- Partner company name has no database uniqueness constraint and the route does not impose one; this was assessed as a data-quality limitation, not an authorization or cross-company substitution vulnerability. Company access grants module-wide partner visibility by the established module design.
- PII in list/detail/search/template output is Jinja-escaped by normal template rendering; no JSON/AJAX partner directory endpoint exists in this primary scope. Partner detail renders PII only after `partners.view` plus the module gate (`app/partners/routes.py:153-165`); company detail requires `partner_companies.view` (`app/partner_companies/routes.py:54-83`).
- Audit calls include actor derivation, entity ID, and before/after snapshots for partner/company/department create-update-lifecycle actions (`app/audit.py:9-27`; `app/partners/routes.py:139,224,247,266`; `app/partner_companies/routes.py:180,202,221,243,346`). Photo attachment/replacement itself has no dedicated audit action; this is a coverage gap but not a confirmed authorization failure.

## Needs verification

- The storage provider’s behavior if `upload_object()` fails after `StorageObject` is flushed cannot be resolved from the partner call chain alone. Verifying whether it can leave an orphaned remote object or an uncommitted `StorageObject` requires a controlled storage-provider failure test, which this batch did not create or run.
- The production logging/proxy configuration was not in Unit 6A’s primary scope. It would establish whether redirect `Location` headers containing presigned URLs are retained beyond ordinary browser history.
- The Partner display-image pipeline’s synchronous Pillow content-format/decompression-bomb exposure is technically confirmed at `app/display_images.py:41-58`, but its vulnerable dependency root cause is foundation-owned (see tool-lead closure below) and is not duplicated as a Unit 6A finding.

## Tool leads closed as false positive/info

- **Pillow/display-image lead — confirmed, cross-referenced rather than duplicated.** Partner/company uploads reach `Image.open()` through `replace_display_image` (`app/display_images.py:43-58`), which accepts an extension allow-list but has no explicit `Image.MAX_IMAGE_PIXELS` configuration or content-based declared-type match. This is the shared synchronous display-image root cause already documented in `.audit/FOUNDATION-B.md` and assigned primarily to the display-image/account review; no distinct Unit 6A root cause was created.
- **Partner archive/deactivate divergence lead — false positive.** The source proves pure delegation for both entities, with identical archive authorization and side effects as recorded under “Explicitly checked and found clean.”
- **Partner object-helper IDOR lead — false positive as an ownership claim.** The helpers discard their `partner` argument (`app/auth/permissions.py:118-139`), but the application’s documented and implemented policy is module-wide Partners visibility; no route incorrectly relies on them to enforce an absent project/tenant boundary.
