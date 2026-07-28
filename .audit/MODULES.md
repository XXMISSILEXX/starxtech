# MODULES.md — Approved audit plan (v2)

Read-only. Supersedes the v1 plan per your review. Structure changes,
risk re-ranking, new batch plan, and the completeness proof are all reflected
below. See `.audit/PRE-FINDINGS.md` for the pre-recorded findings and
`.audit/TOOL-LEAD-MAP.md` for the tool-finding → unit assignment.

Total tracked repo: 553 files, 52 commits. Python: 192 files / ~22.8k LOC.
Templates: 66 files / ~3.0k LOC. JS: 21 files / ~2.0k LOC. 29 Alembic
migrations.

---

## Foundation pass — sequential, before Batch 1 (Bước 3)

### Foundation-A1 — Authorization model

- **Paths**: `app/__init__.py`, `app/config.py`, `app/extensions.py`,
  `app/security.py`, `app/auth/` (`forms.py`, `permissions.py`, `routes.py`),
  `app/permissions/` (`registry.py`, `services.py`, `sync.py`),
  `app/project_memberships.py`, `app/navigation.py`, `app/ui.py`,
  `app/celery_app.py`, `app/celery_worker.py`.
- **~LOC**: ~1,676 (auth 373, permissions 205, project_memberships 125,
  ui 243, config 116, security 84, extensions 13, navigation 72,
  celery_app 68, celery_worker 13, `__init__.py` 249, `branding.py` moved to
  A2 per the split — see below).
- **Scope note**: this is the guard chain, the three-layer authorization
  primitives, CSRF/security-header/rate-limit wiring, and the app factory
  itself — no data model, no audit trail (those are A2).
- **Runs concurrently with**: Unit 12 (Docker/IaC) — see Batch plan.

### Foundation-A2 — Data model & audit trail

- **Paths**: `app/models/` (all 19 files), `app/audit.py`, `app/date_utils.py`,
  `app/branding.py`, `migrations/` (schema-history review, not a line-by-line
  read of all 29 files).
- **~LOC**: ~1,529 (models 1394, audit 49, date_utils 39, branding 23, plus
  migration-history review as a distinct activity, not raw LOC).
- **Why split from A1**: A1 is "can this request proceed"; A2 is "what does
  the request touch and what gets recorded." Splitting keeps each pass
  focused and under ~1,700 LOC. Runs immediately after A1 — depends on
  understanding `TimestampMixin`/`SoftDeleteMixin` usage patterns established
  in A1's read of `app/models/mixins.py`... (mixins.py is itself under
  `app/models/`, included here, not A1).

### Foundation-B — Storage & media processing infrastructure

- Unchanged from v1: `app/storage/`, `app/media_processing/`,
  `app/bulk_downloads/`, `app/display_images.py`. ~1,324 LOC. Runs after A2.

---

## Module audit units — updated table

| # | Module | Paths | ~LOC | Files | Risk | Why this risk | Shared code it depends on | Batch |
|---|---|---|---|---|---|---|---|---|
| 1 | CLI & Ops commands | `app/cli.py`, `scripts/backup_db.sh`, `scripts/backup_uploads.sh`, `scripts/restore_db.sh`, `scripts/start-media-worker.sh`, `docker-entrypoint.sh`, `gunicorn.conf.py` | ~1,400 | 7 | **Critical** | Every destructive/irreversible operation; admin-seeding path; the `security-audit` self-check logic itself; container entrypoint run on every deploy. **New deliverable (PRE-008)**: audit every hardcoded credential/default password/seeded account in `cli.py`, and report exact admin-seeding behavior when the relevant env var is unset. | Foundation-A1, Foundation-A2 | 1 |
| 2 | Admin & RBAC UI | `app/admin/`, `app/admin_storage/`, `app/users/` | ~1,375 py / ~432 html | 8 py / 11 html | **Critical** | User/role/permission management, password reset, project membership admin, storage dashboard+CSV export; `SUPER_ADMIN` bypass in Foundation-A1 makes any escalation bug here total | Foundation-A1, Foundation-A2, Foundation-B (avatar/branding) | 1 |
| 3a | Reports core | `app/reports/__init__.py`, `app/reports/routes.py`, `app/reports/services.py`, `app/projects/` | ~1,458 | 5 | **Critical** | The system's core business object; largest single file in the repo (`reports/services.py`, 894 LOC) is also called into by 3b's `finalize` path — cross-reference required | Foundation-A1, Foundation-A2, Foundation-B | 1 |
| 3b | Report upload flows | `app/reports/create_v2.py`, `app/reports/direct_uploads.py` | ~450 | 2 | **Critical** | **Explicit deliverable**: a side-by-side comparison of this flow against the legacy upload-session routes in `app/projects/routes.py` (3a) — does every check present in one exist in the other? **A concrete divergence is already confirmed, not just suspected** — see PRE-011 in `PRE-FINDINGS.md`: the `daily_report_create_v2` blueprint's endpoint prefix is absent from `require_reports_module_access`'s gated-prefix tuple and the blueprint has no `@bp.before_request` of its own, unlike `projects_bp`/`reports_bp` which get that module-level gate in addition to the same per-project `can_create_report` check both flows share. Confirm actual exploitability (both flows independently deny non-members/VIEWER_ADMIN via the per-project capability check) and decide whether the missing module-gate layer matters in practice. | Foundation-A1, Foundation-A2, Foundation-B, 3a (`reports/services.py`) | 1 |
| 4 | Project Documents | `app/project_documents/` | ~891 py / ~160 html | 4 py / 3 html | **High** | Folder-tree permissions, presigned upload/download/bulk-ZIP, custom-root creation is a "dangerous" permission. Confirmed: has its own `@bp.before_request` module gate (`app/project_documents/routes.py:25-27`). **Explicit deliverable (paired with unit 5)**: line-by-line comparison table of `project_documents/services.py`'s permission-grant function vs `company_media/services.py:78 set_permission` — every check present in one, absent in the other. | Foundation-A1, Foundation-A2, Foundation-B | 2 |
| 5 | Company Media | `app/company_media/` | ~377 py / ~41 html | 4 py / 3 html | **High** | Same presigned-upload/bulk-download/permission-grant pattern as #4, independently implemented (`set_permission`, `app/company_media/services.py:78`). Confirmed: has its own `@bp.before_request` module gate (`app/company_media/routes.py:18-20`). **Must run in the same batch as unit 4** for the paired comparison deliverable. | Foundation-A1, Foundation-A2, Foundation-B | 2 |
| 6a | Partners core | `app/partners/`, `app/partner_companies/`, `app/partner_photos.py` | ~1,245 | 5 | **High** | PII (partner phone/email/photo); dual archive-vs-deactivate endpoints (see `docs/Relation_management_inventigation/ROUTE_AND_UI_PLAN.md`) — confirm both paths enforce identical checks. Confirmed: both blueprints have their own `@bp.before_request` → `can_access_partners_module()`. | Foundation-A1, Foundation-A2, Foundation-B (photo/display-image) | 3 |
| 6b | Partner fields & relations | `app/partner_fields/`, `app/partner_field_collections/`, `app/partner_relations/` | ~845 | 6 | **High** | **Specific deliverable**: cycle/depth handling in the recursive company/department tree at `app/partner_relations/routes.py:145` (`tree` view) and its supporting query — construct or reason about a self-referential/cyclic `CompanyDepartment`/`PartnerRelationship` chain and confirm the tree builder terminates and paginates/limits depth. Confirmed: all three blueprints independently gate via their own `@bp.before_request` → `can_access_partners_module()`. | Foundation-A1, Foundation-A2, Foundation-B | 3 |
| 7 | Attachments | `app/attachments/` | ~157 | 2 | **CRITICAL** (was High) | Hand-rolled per-request authorization in `_authorised()` (`app/attachments/routes.py:94`), serves file bytes directly (`view`/`thumbnail`/`download`). **First task for this unit, before anything else**: confirm whether `attachments.` routes are actually covered by any module gate — its endpoint prefix **is** present in `require_reports_module_access`'s tuple (`app/__init__.py:174`, confirmed by re-reading the source, see completeness table below), so the module gate does apply via the global hook; what remains unverified is whether `_authorised()` itself correctly re-derives project-level report-attachment visibility per attachment, not just "is logged in." | Foundation-A1, Foundation-A2, Foundation-B | 2 |
| 7b | Issues | `app/issues/` | ~439 py / ~154 html | 3 py / 2 html | **High** | **New unit** — see "Completeness proof" below: the original plan bundled Issues with Attachments as one unit; your restructuring instructions renamed that unit to Attachments only and did not give Issues a new home, which is exactly the kind of gap Part 4 asks me to catch and fill rather than silently drop. All-inline-checked, no blueprint-level `before_request` of its own (confirmed by grep) — relies entirely on the global module-gate hook (`issues.` **is** in the gated prefix tuple) plus per-issue `can_view_issue`/`can_edit_persistent_issue`/etc. calls. Placed in Batch 4 to keep Batch 2 at 4 units per your plan; happy to move it if you'd rather it ride with Attachments in Batch 2 (would make that batch 5 units). | Foundation-A1, Foundation-A2, Foundation-B | 4 |
| 8 | Customers & Project Operations | `app/customers/`, `app/project_operations/` | ~1,031 py / ~125 html | 6 py / 12 html | **High** (confirmed, not Medium/High) | Newest code in the repo (Phase 9); contractor assignment lifecycle and project-update timeline are new authorization surfaces on top of the project-membership model. Both blueprints rely solely on the global module-gate hook (`customers.`, `project_operations.` both confirmed in the gated tuple) — no blueprint-level `before_request` of their own. | Foundation-A1, Foundation-A2, Foundation-B | 3 |
| 9 | Dashboard | `app/dashboard/` (`bp` + `api_bp`, two blueprints, two url_prefixes — `/reports/dashboard` and `/api/reports/dashboard`) | ~898 py / ~313 html | 3 py / 4 html | **HIGH** (was Medium) | **Explicit deliverable**: for every dashboard view, compare the HTML variant (`bp`) and the JSON variant (`api_bp`) field-by-field and filter-by-filter. Report any field exposed in JSON that the HTML does not render, and any visibility filter present in one and missing in the other. Both blueprint prefixes (`dashboard.`, `dashboard_api.`) are confirmed in the global module-gate tuple, so the module gate is not the concern here — independent-implementation drift between the two response shapes is. | Foundation-A1, Foundation-A2, Foundation-B | 3 |
| 10 | Account (+ Modules switcher) | `app/account/` (primary deliverable scoped to `app/account/routes.py:61`), `app/modules/`, plus the stray `/media-display-preview` route bound directly on `app` (`app/__init__.py:114-115`, same handler as `app/account/routes.py`) | ~154 py / ~12 html | 6 py / 2 html | **HIGH** for the `routes.py:61` scope; Low/Medium for the rest | **Focused deliverable**: `Image.open(...).verify()` at `app/account/routes.py:61` (and the second `Image.open` at line 62) checks headers without decoding — does not stop decompression bombs or polyglot files. Check for `Image.MAX_IMAGE_PIXELS`/pixel-count limits, re-encode-on-save, content-type enforcement, and where the resulting file is written. **Confirmed by grep**: neither `app/account/routes.py` nor `app/display_images.py` sets `Image.MAX_IMAGE_PIXELS` — only `app/media_processing/pipeline.py:54` does, and that runs in the separate Celery worker process, so it does not protect this synchronous, app-proxied upload path. This compounds with the Pillow CVEs in `TOOL-LEAD-MAP.md` (no `formats=` restriction either, at lines 61-62 and `display_images.py:47,49` — any Pillow-registered format is attempted regardless of claimed extension). `app/modules/` (the module switcher, login-gated only, no module concept applies) and the stray route stay in this unit at their original low priority — a judgment call, flagged for your override. | Foundation-A1, Foundation-B (`display_images.py`) | 4 |
| 11 | Frontend JS | `app/static/js/*.js`, `tests_js/*.test.js` | ~2,012 (+ vendor bundle) | 18 + 3 tests | **Medium** | Client only enforces UX-level limits; every check must have a server-side twin. **Semgrep lead to fold in**: `typescript.react.security.audit.react-unsanitized-method` at `app/static/js/app.js:269` (`insertAdjacentHTML` in `initStatusBadges`) — preliminary read shows `statusIconMarkup()` already regex-validates the icon key and escapes the sprite URL, so likely low risk, but confirm every call site's `data-status-icon-key`/`data-status-icon-sprite` values are always server-rendered from a fixed status enum, never free text. | Foundation-B (comparison target) | 4 |
| 12 | Docker / deploy / IaC | `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `DEPLOY_UBUNTU.md`, `DOCKER_DEPLOY.md`, `gunicorn.conf.py` (cross-ref only, owned by #1), `deploy_backup_2026-07-14_142253/*` (comparison target, see PRE-003) | small | 5 + comparison | **Critical** (elevated — gates Phase 11, runs first) | Runs **concurrently with Foundation-A1**, not after it — shares no code with anything and its answer (is the Celery worker supervised anywhere? what's the actual deploy mechanism? what happens if this machine is lost?) is a Phase-11 go/no-go input, not a code-correctness question. **Deliverables, all specified in `PRE-FINDINGS.md`**: PRE-003 (default values of the 8 `DAILY_REPORT_*` vars when unset, + gunicorn worker count + effective rate-limit multiplier under the backup compose file), PRE-004 (confirm/refute no supervised Celery worker), PRE-006 (inventory every hardcoded environment-specific value in `docker-compose.yml`, produce the `.env.example` needed to externalize them), PRE-009 (how source reaches the server; what's lost if the machine is lost). | — (concurrent with A1) | concurrent w/ A1 |
| 13 | Test suite integrity | `tests/` (all files, including `tests/conftest.py`, `tests/helpers/`) | — | ~40+ test files | **Medium** (goal is not coverage) | **New unit.** Goal: determine how much of the test suite proves anything about *real* endpoints. Deliverables: (a) which tests exercise real registered routes vs. the synthetic `test_project_read`/`test_project_write` routes defined in `tests/conftest.py:30-38`; (b) which tests mock the thing they claim to test; (c) which security-critical functions have only happy-path tests; (d) the list of authorization checks tested only through the dead decorators (`project_read_required`, `project_write_required` — see PRE-002) rather than through a real route — `tests/conftest.py:30-38` is confirmed to be exactly this case already, list any others. | Foundation-A1 (to know what "real route" vs "synthetic" means) | 4 |
| 14 | Template output safety | All 66 Jinja templates under `app/templates/`, cross-referenced against `app/static/js/` for `innerHTML`/`insertAdjacentHTML` sinks | ~3,035 (html) | 66 | **HIGH** (elevated — see PRE-010, this is the only real coverage the template layer gets) | Find every `|safe`, `{% autoescape false %}`, `{{ ... }}` inside a `<script>` block or inside an HTML attribute (especially `href`/`src`), and every place server data reaches the DOM via `innerHTML`/`insertAdjacentHTML` in `app/static/js/`. For each, determine whether the value can contain user-controlled input. **Leads already surfaced by semgrep, to verify not re-discover** (full detail in `TOOL-LEAD-MAP.md`): `app/ui.py:196,199` (`Markup(f"...")` with explicit `escape()` — looks correct, confirm), `app/project_documents/routes.py:303` (`Markup(f"...{archived_url}...")` **without** `escape()`, inconsistent with the `ui.py` pattern two lines away in the same codebase — `archived_url` is built via `url_for()` which percent-encodes, so likely not exploitable today, but confirm and treat the inconsistent pattern itself as worth fixing regardless); 4 `var-in-href` hits (`dashboard/_type_navigation.html:7`, `issues/index.html:10,62`, `modules/index.html:7`) where the href values are `url_for()`-derived, not raw user input — likely false positives, confirm; 1 `var-in-script-tag` hit (`project_documents/permissions.html:66`) using `{{ principal_options|tojson }}` — the correct/safe Flask pattern for JSON-in-script, almost certainly a false positive, confirm and close quickly rather than spend time on it. | Foundation-A1 | 2 |

**Batch assignment** (per your Part 3, with the Issues gap resolved into Batch 4):

- **Foundation-A1 ∥ Unit 12** (concurrent) → **Foundation-A2** → **Foundation-B** (sequential)
- **Batch 1**: 1 (CLI), 2 (Admin), 3a (Reports core), 3b (Upload flows) — all Critical, mutually independent
- **Batch 2**: 4 (Project Documents), 5 (Company Media), 7 (Attachments), 14 (Template safety) — High/Critical
- **Batch 3**: 6a (Partners core), 6b (Partner fields & relations), 8 (Customers & Ops), 9 (Dashboard) — High
- **Batch 4**: 7b (Issues), 10 (Account), 11 (Frontend JS), 13 (Test integrity) — Medium/High, 4 units

---

## Completeness proof (Part 4)

Read directly from `app/__init__.py` (not the directory listing). **22**
`app.register_blueprint(...)` calls, matching exactly 22 blueprint imports at
the top of `register_blueprints()` (my first pass under-counted this at 20-21
in `ARCHITECTURE.md` — corrected here), plus one non-blueprint route bound
directly on `app` (`app/__init__.py:114-115`).

| Blueprint (endpoint-name prefix) | `url_prefix` | `app/__init__.py` registration line | Module-gate mechanism (confirmed by reading the blueprint's own `routes.py`) | Unit |
|---|---|---|---|---|
| `admin.` | `/admin` | 112 | RBAC `@permission_required(...)` per-route; no module gate (correct — not a "module") | 2 |
| `account.` | `/account` | 113 | Login-only, no module concept | 10 |
| *(stray)* `media_display_preview` | `/media-display-preview` | 114-115 | `add_url_rule`, not a blueprint — login-gated only via the global hook; same handler function as `account.` | 10 |
| `admin_storage.` | `/admin/storage` | 116 | RBAC `@permission_required(...)` per-route | 2 |
| `auth.` | *(none)* | 117 | Pre-login by definition (`login` is a public endpoint) | Foundation-A1 |
| `modules.` | `/modules` | 118 | Login-only, module-agnostic switcher (correct — it's the thing that tells a user which modules exist) | 10 |
| `dashboard.` | `/reports/dashboard` | 119 | **Global hook** (`"dashboard."` in `report_endpoints` tuple, `app/__init__.py:174`) | 9 |
| `dashboard_api.` | `/api/reports/dashboard` | 120 | **Global hook** (`"dashboard_api."` in the same tuple) | 9 |
| `users.` | `/users` | 121 | RBAC `@permission_required("users.view")` per-route | 2 |
| `projects.` | `/reports/projects` | 122 | **Global hook** (`"projects."`) | 3a |
| `project_documents.` | `/project-documents` | 123 | Own `@bp.before_request` → `can_access_project_documents()` (`app/project_documents/routes.py:25-27`) | 4 |
| `company_media.` | `/company-media` | 124 | Own `@bp.before_request` → `p.access()` (`app/company_media/routes.py:18-20`) | 5 |
| `customers.` | `/customers` | 125 | **Global hook** (`"customers."`) | 8 |
| `project_operations.` | *(none — routes hardcode their own segments)* | 126 | **Global hook** (`"project_operations."`) | 8 |
| `reports.` | `/reports` | 127 | **Global hook** (`"reports."`) | 3a |
| `daily_report_create_v2.` | `/api/projects/<int:project_id>/daily-reports` | 128 | **Neither** the global hook (its prefix is absent from the `report_endpoints` tuple) **nor** its own `@bp.before_request` — only the per-project `can_create_report()` check inline in every route via a shared `_project()` helper. **Gap confirmed, see PRE-011.** | 3b |
| `issues.` | `/reports/issues` | 129 | **Global hook** (`"issues."`) | 7b |
| `attachments.` | `/attachments` | 130 | **Global hook** (`"attachments."` — confirmed present in the tuple; ARCHITECTURE.md v1 flagged this as unverified, now confirmed covered) | 7 |
| `partners.` | `/partners` | 131 | Own `@bp.before_request` → `can_access_partners_module()` (`app/partners/routes.py:34-38`) | 6a |
| `partner_companies.` | `/partner-companies` | 132 | Own `@bp.before_request` → `can_access_partners_module()` (`app/partner_companies/routes.py:15-17`) | 6a |
| `partner_fields.` | `/partner-fields` | 133 | Own `@bp.before_request` → `can_access_partners_module()` (`app/partner_fields/routes.py:13-15`) | 6b |
| `partner_field_collections.` | `/partner-field-collections` | 134 | Own `@bp.before_request` → `can_access_partners_module()` (`app/partner_field_collections/routes.py:13-15`) | 6b |
| `partner_relations.` | `/partner-relations` | 135 | Own `@bp.before_request` → `can_access_partners_module()` (`app/partner_relations/routes.py:23-25`) | 6b |

Every blueprint maps to exactly one unit. **One gap found and filled**: Issues
(unit 7b, added — see its row in the module table above for why). **One
structural gap confirmed, not filled** (it's a finding, not a plan defect):
`daily_report_create_v2.` bypasses the global module-gate hook — assigned to
unit 3b as its lead deliverable, recorded as PRE-011 in `PRE-FINDINGS.md`.

### `require_reports_module_access` prefix list vs. all registered prefixes

The gate tuple (`app/__init__.py:174`) is exactly:
`("dashboard.", "dashboard_api.", "projects.", "reports.", "issues.", "attachments.", "customers.", "project_operations.")`
— 8 entries, plus the explicit `admin.*` allow-list for project/category admin
endpoints (`app/__init__.py:175-180`).

Of the 22 registered blueprint-name prefixes, 8 are in that tuple (listed
above) and **14 are not**: `admin.`, `account.`, `admin_storage.`, `auth.`,
`modules.`, `users.`, `project_documents.`, `company_media.`,
`daily_report_create_v2.`, `partners.`, `partner_companies.`,
`partner_fields.`, `partner_field_collections.`, `partner_relations.`.

Of those 14: 7 (`project_documents.`, `company_media.`, `partners.`,
`partner_companies.`, `partner_fields.`, `partner_field_collections.`,
`partner_relations.`) compensate with their own `@bp.before_request` module
gate, confirmed by direct grep of each blueprint's `routes.py`. **1**
(`daily_report_create_v2.`) has neither the global hook nor its own gate —
the PRE-011 gap. The remaining 6 (`admin.`, `account.`, `admin_storage.`,
`auth.`, `modules.`, `users.`) are intentionally module-gate-free because
they are not "modules" in this app's sense (they're either pre-login, RBAC-only
admin surfaces, or module-agnostic utility screens) — not gaps.

---

## Directories/paths not read, and why

(Unchanged from v1 — see prior audit note.) `node_modules/`, `.venv/`,
`__pycache__/`, `.pytest_cache/` — vendored/compiled, covered by tool output.
`backups/`, `docker_backup_2026-07-14_131012/` — git-ignored, local-only.
`storage/uploads/`, `tmp/` — git-ignored, empty/local. `secrets/` (beyond
`README.md`) — deliberately not opened. `docs/` — grep-scanned for
cross-reference only, not read file-by-file, treated as historical intent,
never as ground truth over the code.

`deploy_backup_2026-07-14_142253/` is **tracked in git** (added by commit
`2d70dee`, not excluded by the `.gitignore` `docker_backup_*` pattern which
doesn't match its different name) — now upgraded from "anomaly worth a
decision" to an active comparison target for Unit 12 per PRE-003.

## Things that look unfinished or worth a second look at a glance

Everything from v1 stands (dead authorization decorators — PRE-002;
audit-log IP spoofability — PRE-001; `reports_create_legacy_post_rejected`;
the company_media/project_documents duplicate permission-grant logic — now
unit 4+5's explicit paired deliverable; knip/semgrep/trivy tool blind spots
from the first pass, now superseded by real tool output, see
`TOOL-LEAD-MAP.md`; no literal TODO/FIXME markers exist in source).

**New, found during this pass**:
- **PRE-011** (new): `daily_report_create_v2` blueprint has no module-level
  gate, unlike every other reports-module route — see unit 3b and the
  completeness table above.
- `migrations/versions/20260722_0014_three_layer_authorization.py:52-53` and
  `app/cli.py:498` both trip semgrep's `avoid-sqlalchemy-text` rule for
  building raw SQL via string concatenation, but in both cases the
  concatenated values are fixed, hardcoded identifiers (a constant flags
  list; a constant seed-table list), never attacker input, and both are
  reachable only from operator-invoked migrations/CLI commands, never from
  an HTTP route. Recorded so Batch 1 (unit 1) doesn't need to re-derive this
  from scratch, but doesn't need urgent action either — see
  `TOOL-LEAD-MAP.md`.

## Total audit effort estimate

Revised from v1: 2 foundation passes (A1, now run concurrently with Unit 12;
A2; B — 3 sequential/concurrent steps instead of 2) + 16 module units (was
12: split 3→3a/3b, split 6→6a/6b, added 7b/13/14) across 4 batches of ≤4
units each. Rough order of magnitude: **19 deep-read passes** before Bước
6-8. The three explicit paired/comparison deliverables (3a↔3b, 4↔5, HTML↔JSON
in 9) and the two elevated-to-HIGH/CRITICAL units (7, 9, 10-scoped, 14) are
where most of the real time will go, more than raw LOC would suggest.
