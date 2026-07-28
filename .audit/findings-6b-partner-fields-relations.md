# Findings — Unit 6B: Partner fields, collections, and relations

## Summary

- The three registered blueprints are `partner_fields`, `partner_field_collections`, and `partner_relations`; `flask --app run.py routes` confirms all 18 expected endpoint names and paths.
- Every endpoint is first covered by the app-wide login hook (`app/__init__.py:152-167`), then each of these blueprints' own `before_request` module gate, and finally a route-specific `permission_required` check. The module gate requires `modules.partners.access`; route checks require the corresponding `.view`, `.manage`, or `.delete` permission.
- These are global partner-catalogue permissions, not tenant/project/object permissions. The direct-ID routes correctly scope relationship IDs to their company where that parent-child relationship exists; a caller granted the relevant partner-suite permission can intentionally view the complete catalogue.
- Confirmed findings are authenticated data-integrity/lifecycle defects. No anonymous route, SQL injection, cross-company relationship-ID substitution, or write route lacking RBAC was found.
- The department-tree reader has no cycle/depth defence. Its DoS/exception paths require corrupt department rows because the sole HTTP writer currently prevents cycles; this is therefore defence in depth, not a currently web-creatable remote DoS.

Files read: 16 primary files (6 Python blueprint files; 10 matching templates), plus registration/auth/RBAC, models, audit helper, partner field-value service, department writer, migrations, registry, tests, and all required audit context. Files skipped: none in the assigned primary paths. `claude-partial-audit-backup/` was not read or searched.

## Findings

### PARTNER-FIELD-001 — Collection save trusts submitted definition IDs, allowing inactive membership and an unhandled foreign-key failure

- **Severity:** Low
- **Confidence:** High
- **Classification:** Authenticated data-integrity and reliability defect
- **CWE:** CWE-20 (Improper Input Validation)
- **Location:** `app/partner_field_collections/routes.py:82-93`, `app/partner_field_collections/routes.py:114-123`; `app/models/partner.py:130-148`
- **Reachability:** An authenticated user with both `modules.partners.access` and `partner_field_collections.manage` reaches `POST /partner-field-collections/new` or `POST /partner-field-collections/<collection_id>/edit`. Global login runs before the blueprint's module hook (`app/__init__.py:155-167`); the module hook is at `app/partner_field_collections/routes.py:13-16`; the route permission is at `:37` or `:46`.
- **Vulnerable code:**
  ```python
  collection.items[:] = []
  db.session.flush()
  for sort_order, field_id in enumerate(_selected_field_ids(), start=1):
      item = PartnerFieldCollectionItem(
          collection_id=collection.id,
          field_definition_id=field_id,
          sort_order=sort_order,
      )
      _add_with_sqlite_id(item)
      collection.items.append(item)
  ```
  (`app/partner_field_collections/routes.py:82-91`)

  ```python
  for raw in request.form.getlist("field_definition_ids"):
      if raw.isdigit():
          field_id = int(raw)
          if field_id not in seen:
              seen.add(field_id)
              result.append(field_id)
  ```
  (`app/partner_field_collections/routes.py:117-123`)

  The only server-side form source used for rendering is active definitions:
  ```python
  PartnerFieldDefinition.query.filter(PartnerFieldDefinition.is_active.is_(True))
  ```
  (`app/partner_field_collections/routes.py:99-103`), but `_selected_field_ids()` neither retrieves the submitted definitions nor verifies that they exist or remain active.
- **Impact:** A valid but inactive definition can be put back into an active collection despite being omitted from the UI. A nonexistent numeric ID reaches the foreign key at `app/models/partner.py:143-148`; `_save_collection()` has no `IntegrityError` handling, so PostgreSQL will reject the transaction and Flask will produce a server error. The foreign key prevents persistent dangling data, but not the request failure or inactive-definition integrity violation.
- **Remediation:** Resolve all submitted IDs in one query; reject missing and inactive definitions before mutating `collection.items`, and return the form with a validation error. Keep the existing deduplication and database unique constraint.
- **Effort:** S

### PARTNER-FIELD-002 — Field-definition labels are not unique

- **Severity:** Info
- **Confidence:** High
- **Classification:** Data-integrity defect
- **CWE:** CWE-20 (Improper Input Validation)
- **Location:** `app/partners/services.py:214-248`; `app/models/partner.py:96-110`
- **Reachability:** An authenticated `partner_fields.manage` user can create or edit definitions through the protected `/partner-fields/new` and `/<field_id>/edit` routes (`app/partner_fields/routes.py:58-91`).
- **Vulnerable code:**
  ```python
  existing = PartnerFieldDefinition.query.filter(PartnerFieldDefinition.field_key == field_key)
  if field:
      existing = existing.filter(PartnerFieldDefinition.id != field.id)
  if field_key and existing.first():
      errors.append("Mã trường đã tồn tại.")
  ```
  (`app/partners/services.py:224-228`)

  ```python
  label = db.Column(db.String(255), nullable=False)
  field_key = db.Column(db.String(120), nullable=False, unique=True)
  ```
  (`app/models/partner.py:99-102`)
- **Impact:** The required globally unique key is correctly enforced, but two different keys can use the same displayed label. This can cause ambiguous collection and partner-form labels, but does not bypass authorization or reinterpret already saved values: values retain label/key/type snapshots (`app/models/partner.py:167-181`, `app/partners/services.py:284-291`).
- **Remediation:** If label uniqueness is a product invariant, validate and constrain a normalized label. Otherwise document that labels may repeat and rely on the unique field key for identity.
- **Effort:** S

### PARTNER-FIELD-003 — Collection edit silently ignores an operator's request to deactivate

- **Severity:** Low
- **Confidence:** High
- **Classification:** Data-integrity/lifecycle defect
- **CWE:** CWE-841 (Improper Enforcement of Behavioral Workflow)
- **Location:** `app/partner_field_collections/routes.py:66-95`; `app/templates/partner_field_collections/form.html:20-25`
- **Reachability:** An authenticated `partner_field_collections.manage` user can edit any global collection through `POST /partner-field-collections/<collection_id>/edit` after the login and partners-module gates.
- **Vulnerable code:**
  ```python
  <input class="form-check-input" type="checkbox" name="is_active" id="is_active" {% if collection.is_active %}checked{% endif %}>
  ```
  (`app/templates/partner_field_collections/form.html:22`)

  ```python
  collection.is_active = request.form.get("is_active", "on") == "on"
  ```
  (`app/partner_field_collections/routes.py:81`)
- **Impact:** Browsers omit an unchecked checkbox. The fallback converts that omission to `True`, so an active collection cannot be made inactive through the edit form; it remains available to `active_field_collections()` (`app/partners/services.py:40-45`). The dedicated deactivate route is separately protected and works, so this is not an RBAC bypass.
- **Remediation:** Treat a missing checkbox as false, matching `save_field_definition()`'s `form.get("is_active") == "on"` semantics at `app/partners/services.py:247`.
- **Effort:** S

### PARTNER-REL-001 — Multiple relationship rows bypass the partner-parent cycle check

- **Severity:** Low
- **Confidence:** High
- **Classification:** Authenticated data-integrity defect
- **CWE:** CWE-841 (Improper Enforcement of Behavioral Workflow)
- **Location:** `app/partner_relations/routes.py:216-274`, `app/partner_relations/routes.py:490-507`; `app/models/partner.py:187-215`
- **Reachability:** An authenticated user with `modules.partners.access` and `partner_relations.manage` can use the registered `POST /partner-relations/company/<company_id>/manage` endpoint. The handler validates both supplied partner IDs against that company's active partners (`app/partner_relations/routes.py:218-233`), but permits more than one row for the same `partner_id`.
- **Vulnerable code:**
  ```python
  for row in _relationship_rows(company_id):
      if current_relationship and row.id == current_relationship.id:
          continue
      if row.parent_partner_id:
          parent_by_partner.setdefault(row.partner_id, row.parent_partner_id)
  parent_by_partner[partner_id] = parent_partner_id
  ```
  (`app/partner_relations/routes.py:493-499`)

  ```python
  return query.order_by(
      PartnerRelationship.department.asc(),
      PartnerRelationship.display_order.asc(),
      Partner.full_name.asc(),
      PartnerRelationship.id.asc(),
  ).all()
  ```
  (`app/partner_relations/routes.py:315-320`)

  The model has no unique constraint for `(company_id, partner_id)`; its only relationship-table uniqueness declaration is absent (`app/models/partner.py:187-215`).
- **Impact:** The first ordered row for a partner silently becomes that partner's sole edge for cycle detection. For example, with existing active rows `A -> B` and then `A -> C`, a subsequent `C -> A` is tested as `C -> A -> B` and accepted although the stored graph also contains `A -> C -> A`. This is a real reporting-hierarchy cycle, but it does not trigger the department-tree recursion because that renderer follows `CompanyDepartment.parent_department_id`, not `parent_partner_id` (`app/partner_relations/routes.py:323-355`).
- **Remediation:** Define whether multiple parents are valid. If they are, traverse every relevant edge when checking a proposed edge; if not, enforce an appropriate unique constraint and validate conflicts. Preserve the existing legitimate multiple-row use only when its parent is identical or non-hierarchical.
- **Effort:** M

### PARTNER-REL-002 — Archived-company relationship pages remain directly readable

- **Severity:** Low
- **Confidence:** High
- **Classification:** Authenticated information disclosure / lifecycle inconsistency
- **CWE:** CWE-200 (Exposure of Sensitive Information to an Unauthorized Actor)
- **Location:** `app/partner_relations/routes.py:67-81`, `:145-160`, `:510-518`, compared with `:38-49`
- **Reachability:** Any authenticated holder of `modules.partners.access` and `partner_relations.view` can request a known archived `company_id` on `/partner-relations/company/<id>` or `/partner-relations/company/<id>/tree`. This is not an object-ownership bypass—the permission is intentionally module-wide—but it bypasses this module's own archive visibility boundary.
- **Vulnerable code:**
  ```python
  query = Company.query.filter(Company.deleted_at.is_(None))
  ```
  (`app/partner_relations/routes.py:38`)

  ```python
  def _company_or_404(company_id):
      return Company.query.filter(Company.id == company_id).first_or_404()
  ```
  (`app/partner_relations/routes.py:510-511`)

  Both direct read routes call that unfiltered helper:
  ```python
  company = _company_or_404(company_id)
  relationships = _relationship_rows(company.id, request.args.get("q", ""), request.args.get("department", ""))
  ```
  (`app/partner_relations/routes.py:70-71`, `:148-150`)
- **Impact:** Archive hides a company from the relation index yet does not revoke its names, department/position hierarchy, relationship notes, or tree data for a user who knows or retains the ID. Mutation is blocked by `_require_active_company_for_mutation()` (`app/partner_relations/routes.py:514-518`), so the issue is read exposure only.
- **Remediation:** Use an active-record query for normal relation reads, or make archived access an explicit, separately authorized view with clear UI/state handling.
- **Effort:** S

### PARTNER-REL-003 — Department-tree traversal can hang or exhaust recursion on corrupt hierarchy data

- **Severity:** Low
- **Confidence:** High
- **Classification:** Defence-in-depth gap; data-dependent denial of service / recursion exception
- **CWE:** CWE-674 (Uncontrolled Recursion)
- **Location:** `app/partner_relations/routes.py:323-392`; `app/models/partner.py:29-50`
- **Reachability:** An authenticated `partner_relations.view` user can trigger the tree route and its `q`/`department` filters. A malformed cycle must already exist in `company_departments`; the only current HTTP writer prevents such cycles (see Tree analysis), so the condition is not web-creatable through the reviewed routes.
- **Vulnerable code:**
  ```python
  "children": [build_department(child) for child in sorted(by_parent.get(department.id, []), key=lambda item: (item.display_order, item.name))],
  ```
  (`app/partner_relations/routes.py:341-350`)

  ```python
  while current:
      matching_ids.add(current)
      parent = by_id.get(current)
      current = parent.parent_department_id if parent else None
  ```
  (`app/partner_relations/routes.py:373-377`)

  ```python
  while pending:
      current = pending.pop()
      for child in by_parent.get(current, []):
          result.add(child.id)
          pending.append(child.id)
  ```
  (`app/partner_relations/routes.py:387-391`)
- **Impact:** With corrupt data, a selected cyclic department makes `_department_subtree_ids()` loop indefinitely; a matching search term makes the ancestor walk loop indefinitely; and selected-tree construction recursively repeats until `RecursionError`. The tree endpoint loads all departments/members for a company and applies no depth or pagination cap, so a very deep but acyclic hierarchy can also exceed Python's recursion limit.
- **Remediation:** Add visited sets to both iterative traversals and to the recursive builder (or replace it with an iterative/depth-capped builder); define an error/omission policy for corrupt/orphaned rows. Database foreign keys alone cannot prevent cycles.
- **Effort:** M

## Tree termination and cycle analysis

### Database and write-side protections

`CompanyDepartment.parent_department_id` is only a self-referential foreign key:

```python
parent_department_id = db.Column(
    db.BigInteger,
    db.ForeignKey("company_departments.id", ondelete="SET NULL"),
    nullable=True,
    index=True,
)
```
(`app/models/partner.py:39-44`). The table has a unique `(company_id, name)` constraint (`:31-33`), but no self-parent check, no recursive/cycle constraint, and no trigger. The migration creates the same bare FK (`migrations/versions/20260709_0006_add_company_departments.py:20-41`). It therefore prevents only a nonexistent parent, not `A -> A`, `A -> B -> A`, or a longer cycle.

The sole HTTP writer is the department save helper in `partner_companies`, not this blueprint. It verifies same-company and active parents, rejects a direct self-parent, and rejects a descendant parent:

```python
elif parent.company_id != company.id:
    errors["parent_department_id"] = "Phòng ban cấp trên phải thuộc cùng công ty."
...
if department.id is not None and parent_id == department.id:
    errors["parent_department_id"] = "Phòng ban không thể là cấp trên của chính nó."
elif department.id is not None and parent_id in _department_descendant_ids(company.id, department.id):
    errors["parent_department_id"] = "Không thể chọn phòng ban con làm phòng ban cấp trên."
```
(`app/partner_companies/routes.py:319-329`). Its descendant traversal does track visited IDs:

```python
if child_id in descendants:
    continue
descendants.add(child_id)
pending.extend(children_by_parent.get(child_id, []))
```
(`app/partner_companies/routes.py:362-370`). Thus the reviewed HTTP write path is safely terminating and blocks both direct and indirect cycles, but the database does not provide equivalent protection for pre-existing/manual/CLI/migration corruption.

### Read-side behavior and manual traces

The tree reader has no recursive CTE, no recursion-depth maximum, no visited set, no pagination, and no result limit. It executes bounded-count but unbounded-size `.all()` queries for company departments, active relationship rows, and active members (`app/partner_relations/routes.py:323-326`, `:432-446`), plus duplicate relationship and department loads in `tree()` / template setup (`:148-160`). It is not an N+1 traversal in the reviewed tree template, but memory and CPU grow with the full company graph.

| Corrupt graph / input | Execution trace | Result |
|---|---|---|
| `A -> A`, `?department=A` | `_visible_department_ids()` calls `_department_subtree_ids(departments, A)` (`:360-362`); `pending=[A]`; pop A; child A; append A; repeat. | Infinite loop / worker hang. |
| `A -> A`, `?q=<matches A>` | ancestor loop starts `current=A`; adds A; reloads A's parent A; repeats. | Infinite loop / worker hang. |
| `A -> A`, selected builder after bypassing prior loop | `build_department(A)` creates child list containing `build_department(A)` indefinitely. | `RecursionError` / 500. |
| `A -> B -> A`, `?department=A` | `pending=[A] -> [B] -> [A] -> ...` in `:387-391`. | Infinite loop / worker hang. |
| `A -> B -> A`, `?q=<matches A>` | `current=B -> A -> B -> ...` in `:373-377`. | Infinite loop / worker hang. |
| `A -> B -> A`, explicit selected build | `build(A) -> build(B) -> build(A) -> ...`. | `RecursionError` / 500. |
| `A -> B -> C -> A` | The same paths repeat `A, B, C` indefinitely in the subtree/ancestor loops or recursion. | Infinite loop for filters; recursion exception for builder. |
| Orphaned `A.parent_department_id=missing` | `by_parent[missing]` receives A; default roots are only `by_parent[None]`, so A is omitted. A direct `department=A` selection constructs A and terminates if its children are acyclic. | Safely terminates but silently hides orphaned tree branches in the default tree. |
| Duplicate child edge | `parent_department_id` is scalar, so one legitimate row has one parent. The query creates one `by_parent` entry per department (`:330-332`); duplicate ID rows are impossible under the primary key. | No duplicate child produced by ordinary relational data. |
| Deep acyclic hierarchy | `build_department` adds one Python call frame per depth with no cap. | Data-dependent `RecursionError` around the interpreter recursion limit; all nodes are still loaded first. |

**Verdict:** **data-dependent denial of service / recursion exception**, not safely terminating. It is presently a **defence-in-depth gap** because the current HTTP department writer blocks cycles. `PartnerRelationship.parent_relationship_id` is a dead column for this concern: no reviewed route/service reads or writes it; the tree follows department parents only. The separately stored `parent_partner_id` graph is cycle-checkable but has the distinct duplicate-row bypass in PARTNER-REL-001; it is not recursively rendered by this tree.

## Explicitly checked and found clean

- Blueprint registration is explicit and live: `register_blueprints()` imports and registers all three at `app/__init__.py:99-101,133-135`; each blueprint's actual endpoint names were independently listed by Flask.
- Global request order was traced: `require_login` runs at `app/__init__.py:155-167`, then these blueprints' own `@bp.before_request` hooks at `partner_fields/routes.py:13-16`, `partner_field_collections/routes.py:13-16`, and `partner_relations/routes.py:23-26`. `can_access_partners_module()` requires an authenticated user with `modules.partners.access` (`app/auth/permissions.py:68-70`).
- Each mutating route has RBAC: definitions/reorder use `partner_fields.manage`; collections use `partner_field_collections.manage`; relation create/edit uses `partner_relations.manage` and relation archive uses `partner_relations.delete`. View-only roles cannot mutate through hidden UI controls because decorators enforce checks server-side (`app/permissions/services.py:31-39`).
- Field-definition type input is server allow-listed (`FIELD_TYPES`, `app/partners/services.py:12-23`); key uniqueness is both validated and database-constrained (`:224-228`, `app/models/partner.py:101`). Options are normalized by trim/case-insensitive dedupe (`app/partners/services.py:251-259`).
- Definition edits do not rewrite historic field snapshots: persisted values carry snapshot label/key/type/group fields (`app/models/partner.py:167-181`), and partner display consumes those snapshots (`app/partners/services.py:153-171,284-291`). There is no field-definition delete route; deactivation is audited (`app/partner_fields/routes.py:94-103`).
- Collection duplicate submitted IDs are deduplicated in the request (`app/partner_field_collections/routes.py:114-123`) and the database also has `uq_partner_field_collection_field` (`app/models/partner.py:130-148`). Collection-item replacement is transactionally committed with its audit record; the model intentionally hard-deletes/rebuilds item membership and has no soft-delete state.
- Relation form handling validates source and parent partners against the target company's active partner set, rejects self-parenting, constrains relationship type to `RELATIONSHIP_TYPES`, and scopes edit/delete IDs to `(relationship_id, company_id)` (`app/partner_relations/routes.py:216-251,290-295`). Cross-company client ID substitution was not confirmed.
- Relation writes and deletes emit audit records with actor from `current_user`, entity target, and old/new state (`app/partner_relations/routes.py:97-99,117-122,136-140`; `app/audit.py:9-27`). Field and collection creates/updates/deactivations likewise audit before their same-session commits.
- Relation views deliberately expose only module-wide organization data to `partner_relations.view`; direct department summary loads the department's own company and filters active departments/non-archived companies (`app/partner_relations/routes.py:166-190`). There is no separate customer/project scope in the partner data model, so lack of such a check is not reported as an IDOR.
- The legacy `GET, POST /partner-relations/company/<company_id>/edit` route is registered but only redirects (`app/partner_relations/routes.py:193-196`); it does not mutate state.

## Needs verification

- The production effect of an invalid collection field-definition ID should be exercised only against an isolated PostgreSQL test database: SQLite tests may not enforce foreign keys identically. Source establishes the unhandled constraint path, but this batch did not mutate any database or create a PoC.
- Product intent is needed to decide whether duplicate field labels and repeated non-hierarchical relationship rows are supported catalogue behavior. The security facts above are source-confirmed; only the desired invariant is open.
- Existing production data was not inspected under the batch rules. If any department hierarchy is already corrupt or unusually deep, PARTNER-REL-003 becomes immediately reachable by ordinary `partner_relations.view` users.
- Partner form integration is owned by Unit 6A. Cross-reference `PARTNER-004` for the independently confirmed separate root cause that `app/partners/services.py` accepts inactive field definitions, duplicate values, and arbitrary select/multi-select values; it is intentionally not duplicated here.

## Tool leads closed as false positive/info

- No Semgrep/pip-audit tool-lead row in `.audit/TOOL-LEAD-MAP.md` was assigned specifically to Unit 6B.
- The Unit-6B ENDPOINTS leads were independently confirmed from source, not adopted on trust: unchecked collection definition IDs are PARTNER-FIELD-001; the reader's missing cycle guards are PARTNER-REL-003; and the duplicate-row weakness in partner-parent cycle detection is PARTNER-REL-001.
- No raw SQL, shell execution, raw model JSON serialization, presigned-storage handling, or XSS sink exists in the assigned primary blueprint/template files. Jinja rendering uses normal escaped expressions; no `|safe` or `Markup` use was found in the assigned templates.

## Counts and completion notes

| Severity | Count |
|---|---:|
| Critical | 0 |
| High | 0 |
| Medium | 0 |
| Low | 5 |
| Info | 1 |
| Needs verification | 3 |

- Unread primary files: none.
- Related preparation items, not duplicate finding IDs: `.audit/ENDPOINTS.md` items 21, 29, and 32. No existing Batch 1/2 finding ID was reused.
- Every finding above includes exact file:line evidence. No PoC was created, no test was run, and no application/configuration/migration/template/database file was changed.
