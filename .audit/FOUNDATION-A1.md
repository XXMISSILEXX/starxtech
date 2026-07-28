# FOUNDATION-A1.md — Authorization model deep pass

Read-only. Scope: `app/__init__.py`, `app/config.py`, `app/extensions.py`,
`app/security.py`, `app/auth/` (`__init__.py`, `forms.py`, `permissions.py`,
`routes.py`), `app/permissions/` (`__init__.py`, `registry.py`,
`services.py`, `sync.py`), `app/project_memberships.py`,
`app/navigation.py`, `app/ui.py`, `app/celery_app.py`, `app/celery_worker.py`.
Every file in this list was read in full. Nothing outside this list was
read for this pass except where explicitly cited as a one-line lookup to
resolve a cross-reference (e.g. confirming what a blueprint's own
`before_request` calls into).

---

## 1. Middleware / `before_request` / guard chain

Registered in `create_app()`, `app/__init__.py:69-75`, in this exact order:

```
register_blueprints(app)          # :69
register_health_route(app)        # :70
register_trusted_host_guard(app)  # :71
register_auth_guard(app)          # :72
register_security_headers(app)    # :73
register_upload_error_handlers(app) # :74
register_template_helpers(app)    # :75
```

Flask does not execute hooks in blueprint-registration order — it executes
all `@app.before_request` functions in the order they were *added* to the
app (i.e., registration-function-call order above), and all
`@app.after_request` functions in the reverse of that. So the actual
request-time order is:

1. **`require_trusted_host`** (`app/__init__.py:200-204`, registered by
   `register_trusted_host_guard`, called at line 71) — **only registered at
   all if `TRUSTED_HOSTS` is non-empty** (`app/__init__.py:193-195`:
   `configured_hosts = set(app.config.get("TRUSTED_HOSTS", ())); if not
   configured_hosts: return`). If registered, it runs first, before login,
   and `abort(400)`s any request whose `Host` header (scheme/port stripped)
   isn't in the configured set plus `{"127.0.0.1", "localhost", "::1"}`
   (`app/__init__.py:198`, comment explains this loopback allowance is for
   Docker's healthcheck, which never traverses Cloudflare). **Verdict:
   CONFIRMED — this hook applies to every route, no exceptions, when
   `TRUSTED_HOSTS` is set; when unset, it does not exist at all (not "runs
   but always passes" — the function is never registered).**
2. **`require_login`** (`app/__init__.py:155-167`, registered by
   `register_auth_guard`, called at line 72) — runs second. Public
   endpoints, exact set: `{"auth.login", "health", "healthz", "static"}`
   (`app/__init__.py:153`). Also passes through when `request.endpoint is
   None` (`app/__init__.py:159-160`, comment: "Let Flask produce a real 404
   for removed/unknown routes instead of turning obsolete URLs into login
   redirects"). Otherwise: authenticated → `None` (continue); unauthenticated
   → `redirect(url_for("auth.login", next=request.full_path.rstrip("?")))`
   (`app/__init__.py:167`). **Verdict: CONFIRMED — applies to literally every
   registered endpoint except the 4 public ones and endpoint-less 404s.
   There is no blueprint or route that can opt out of this hook** (Flask
   before_request hooks registered on `app`, not on a blueprint, cannot be
   bypassed per-blueprint).
3. **`require_reports_module_access`** (`app/__init__.py:169-189`, same
   registration call) — runs third, immediately after login. Full logic,
   quoted:
   ```python
   if not current_user.is_authenticated:
       return None
   endpoint = request.endpoint or ""
   report_endpoints = ("dashboard.", "dashboard_api.", "projects.", "reports.", "issues.", "attachments.", "customers.", "project_operations.")
   is_report_admin = endpoint in {
       "admin.projects_index", "admin.projects_new", "admin.projects_edit",
       "admin.projects_archive", "admin.projects_reporters", "admin.projects_memberships", "admin.categories_index",
       "admin.categories_edit", "admin.categories_activate", "admin.categories_deactivate",
       "admin.categories_delete",
   }
   if endpoint.startswith(report_endpoints) or is_report_admin:
       from app.auth.permissions import REPORTS_MODULE_DENY_MESSAGE, can_access_reports_module
       if not can_access_reports_module(current_user):
           abort(403, description=REPORTS_MODULE_DENY_MESSAGE)
   ```
   (`app/__init__.py:176-189`). **Verdict: CONFIRMED to apply only to the 8
   endpoint-name prefixes in `report_endpoints` plus the 11 explicitly named
   `admin.*` endpoints — see §2 for the full per-blueprint table.** This
   hook is a no-op for every other blueprint; it is not a general
   "is this user allowed here" check.
4. **`add_security_headers`** (`app/__init__.py:208-236`, `@app.after_request`,
   registered by `register_security_headers` at line 73) — runs on the way
   out, applies to every response regardless of status code (it's an
   `after_request`, which Flask runs even for error responses, unless the
   error occurred before the request context was fully set up). Uses
   `.setdefault(...)` for every header (`app/__init__.py:221,233,234,235`) —
   **a view that sets its own CSP/`X-Frame-Options` would win**; none found
   in this pass, but this is a per-view thing to watch for in later units,
   not verified exhaustively here.
5. **`too_large`** (`app/__init__.py:241-249`, `@app.errorhandler(RequestEntityTooLarge)`,
   registered by `register_upload_error_handlers` at line 74) — not a
   `before_request`/`after_request`, an exception handler. Fires whenever a
   request body exceeds `MAX_CONTENT_LENGTH` (computed at
   `app/__init__.py:44-45` from `MAX_UPLOAD_MB`, default 10 MB — this is a
   **global** Flask/Werkzeug content-length cap, separate from and in
   addition to the per-module `DAILY_REPORT_MAX_*`/`STORAGE_MAX_*` limits
   read by the storage layer). Returns JSON 413 for JSON-accepting or
   `/presign`/`/complete`-suffixed requests, otherwise a plain 413 response;
   always sets `Cache-Control: no-store` (`app/__init__.py:248`).

**No other `before_request`/`after_request`/global `errorhandler` exists
anywhere in this scope.** Confirmed by reading every file in scope in full —
`app/auth/routes.py`, `app/permissions/*.py`, `app/navigation.py`,
`app/ui.py`, `app/celery_app.py`, `app/celery_worker.py` register none.
**There is no global `@app.errorhandler(500)` or
`@app.errorhandler(Exception)` in this codebase** — see §6.

Per-blueprint `@bp.before_request` hooks exist independently of the global
chain above and run *in addition to* it, after it (Flask evaluates
app-level before_request functions, then blueprint-level ones, for the
blueprint owning the matched route). Full enumeration in §2.

---

## 2. Per-blueprint module-gate status — all 22 blueprints, proven

Confirmed by reading `app/__init__.py:88-135`'s `register_blueprints()` in
full (22 `app.register_blueprint(...)` calls, `app/__init__.py:112-135`,
matching 22 blueprint imports at `app/__init__.py:89-110`) and by grepping
`before_request` in every one of the 22 blueprints' `routes.py` files
(`app/reports/create_v2.py` checked separately since it's a 23rd file
registered as its own blueprint from within the `reports` package).

| Blueprint | `app/__init__.py` registration | Gate mechanism | Proof |
|---|---|---|---|
| `dashboard.` | :119 | Global hook (`"dashboard."` in tuple, :179) | — |
| `dashboard_api.` | :120 | Global hook (`"dashboard_api."` in tuple, :179) | — |
| `projects.` | :122 | Global hook (`"projects."` in tuple, :179) | — |
| `reports.` | :127 | Global hook (`"reports."` in tuple, :179) | — |
| `issues.` | :129 | Global hook (`"issues."` in tuple, :179); own blueprint has **no** `before_request` (grep confirmed) | — |
| `attachments.` | :130 | Global hook (`"attachments."` in tuple, :179); own blueprint has **no** `before_request` — per-object check is `_authorised()`, `app/attachments/routes.py:94-97`, called per-route, not a blueprint gate | — |
| `customers.` | :125 | Global hook (`"customers."` in tuple, :179) | — |
| `project_operations.` | :126 | Global hook (`"project_operations."` in tuple, :179) | — |
| `partners.` | :131 | Own `@bp.before_request` | `app/partners/routes.py:34-38`: `if not can_access_partners_module(): abort(403, ...)` |
| `partner_companies.` | :132 | Own `@bp.before_request` | `app/partner_companies/routes.py:15-18` |
| `partner_fields.` | :133 | Own `@bp.before_request` | `app/partner_fields/routes.py:13-16` |
| `partner_field_collections.` | :134 | Own `@bp.before_request` | `app/partner_field_collections/routes.py:13-16` |
| `partner_relations.` | :135 | Own `@bp.before_request` | `app/partner_relations/routes.py:23-26` |
| `project_documents.` | :123 | Own `@bp.before_request` | `app/project_documents/routes.py:25-27`: calls `can_access_project_documents()` (`app/project_documents/permissions.py:21-23`), which is a thin re-export of `app.auth.permissions.can_access_project_documents_module` — same underlying check, not a divergent implementation |
| `company_media.` | :124 | Own `@bp.before_request` | `app/company_media/routes.py:18-20`: calls `p.access(current_user)` = `app/company_media/permissions.py:36 access()`, the same function `app.auth.permissions.can_access_company_media_module` itself delegates to |
| `admin.` | :112 | Not module-gated (not global hook, no own `before_request`) — RBAC `@permission_required(...)` per-route instead (`app/permissions/services.py:31-38`), except the 11 endpoints explicitly named in the global hook's `is_report_admin` set (:180-185), which get **both** | Confirmed by grep — no `before_request` in `app/admin/routes.py` |
| `admin_storage.` | :116 | Not module-gated — RBAC `@permission_required("storage.dashboard.view"/"...export")` per-route | No `before_request` |
| `users.` | :121 | Not module-gated — RBAC `@permission_required("users.view")` per-route | No `before_request` |
| `account.` | :113 | Not module-gated — login-only (this screen has no "module" concept; every authenticated user has an account) | No `before_request` |
| `auth.` | :117 | Pre-login by construction — `auth.login` is one of the 4 public endpoints | No `before_request` (would be meaningless before login) |
| `modules.` | :118 | Not module-gated — login-only; this *is* the module switcher, it must be reachable to tell a user which modules exist for them | No `before_request` |
| `daily_report_create_v2.` | :128 | **Neither** the global hook (`"daily_report_create_v2."` is absent from the tuple at :179) **nor** its own `@bp.before_request`. **PRE-011 CONFIRMED, not refuted.** Every route does call a shared per-project check — `_project()` (`app/reports/create_v2.py:29-35`) → `can_create_report(current_user, project.id)` (`app/auth/permissions.py`, delegates to `user_has_project_capability(..., "can_create_reports")`, `app/project_memberships.py:78-89`) — but this is a per-project capability check, not a module-access check, and it is the *only* check on this blueprint. | Confirmed by reading `app/reports/create_v2.py` in full (135 lines) — no `before_request`, no import of `can_access_reports_module` anywhere in the file |

**Stray non-blueprint route**: `/media-display-preview`
(`app/__init__.py:114-115`, `app.add_url_rule(...)`, handler
`app.account.routes.media_display_preview`) — not a blueprint, so no
blueprint-level gate is possible; it is still subject to the global
`require_login` hook (its endpoint name `"media_display_preview"` doesn't
start with any gated prefix and isn't in the public set, so login is
required, module gate is not).

**Totals**: 7 blueprints self-gate via their own `before_request`
(`partners`, `partner_companies`, `partner_fields`,
`partner_field_collections`, `partner_relations`, `project_documents`,
`company_media`). 8 blueprint-name prefixes are covered by the global hook
(`dashboard.`, `dashboard_api.`, `projects.`, `reports.`, `issues.`,
`attachments.`, `customers.`, `project_operations.`). 6 are intentionally
ungated at the module level because they are RBAC-only or pre-module
surfaces (`admin.`, `admin_storage.`, `users.`, `account.`, `auth.`,
`modules.`). **1 has no gate at all where every sibling in its family does**:
`daily_report_create_v2.`.

---

## 3. Authentication

Session-based via Flask-Login (`login_manager = LoginManager()`,
`app/extensions.py:10`; `login_manager.init_app(app)`, `app/__init__.py:57`;
`login_manager.login_view = "auth.login"`, `app/__init__.py:60`).

- **Login**: `app/auth/routes.py:18-49`. `LoginForm` (`app/auth/forms.py:8-12`,
  WTForms via Flask-WTF, CSRF applies since `CSRFProtect` is global —
  `app/extensions.py:11`, `csrf.init_app(app)` at `app/__init__.py:58`).
  Looks up by username OR email (`app/auth/routes.py:27-32`,
  `User.query.filter(or_(User.username == login_value, User.email ==
  login_value))`). Password check: `user.check_password(...)` →
  `check_password_hash` (Werkzeug) — did not re-read `app/models/user.py`
  in this pass (out of A1 scope, covered in A2), citing from the earlier
  architecture pass only for context, not as a re-verified claim here.
  Failed login is audit-logged (`log_audit("auth.login_failed", ...)`,
  `app/auth/routes.py:35`) **before** committing — note the login attempt's
  raw `login_value` (attacker-controlled) is stored verbatim in
  `AuditLog.new_values_json` (`app/auth/routes.py:35`,
  `new_values={"login": login_value}`) — this is a username/email string,
  not a password, so not a credential leak, but it is unvalidated free text
  written to the audit log on every failed attempt; not flagged as a
  finding here (out of scope for "what leaks"), noted for unit 13's audit-log
  review.
  Inactive users are blocked post-authentication (`app/auth/routes.py:40-42`,
  checked *after* password verification, so a disabled account's password
  is still checked before the 403 — timing-wise this doesn't reveal whether
  an account exists any differently than an active one, since both
  branches require a correct password first).
- **Session establishment**: `login_user(user, remember=form.remember.data)`
  (`app/auth/routes.py:46`) — standard Flask-Login, signs the user ID into
  the session cookie using `SECRET_KEY` via itsdangerous (Flask's built-in
  session interface). **No JWT is used anywhere in this scope** — confirmed
  by reading every file in scope, no `jwt`/`itsdangerous.Serializer(...)`
  custom usage, only Flask's default cookie session.
- **Session cookie flags**: read in `app/config.py` (in A1 scope as
  `Config`), not re-derived here since `app/config.py` is listed in this
  unit's file set — `SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SAMESITE`,
  `SESSION_COOKIE_SECURE` are all environment-driven with defaults `true`,
  `"Lax"`, `false` respectively (`app/config.py`, `SESSION_COOKIE_*` block).
  `SESSION_COOKIE_SECURE` defaulting to `false` is a real footgun for a
  developer who forgets to set it in a real `.env` for production — but
  `production_configuration_errors()` (`app/security.py`, in scope) **does**
  hard-fail startup if `APP_ENV == "production"` and
  `SESSION_COOKIE_SECURE` is falsy (checked and quoted in §6/§7).
- **Expiry**: no explicit `PERMANENT_SESSION_LIFETIME` override found
  anywhere in `app/config.py` in this scope — Flask-Login's default
  behavior applies: non-remembered sessions expire when the browser session
  ends (session cookie, no explicit expiry); `remember=True` sets a
  longer-lived cookie via Flask-Login's own `REMEMBER_COOKIE_DURATION`
  default (also not overridden here). **Did not read `app/models/user.py`
  in this pass** to confirm whether `last_login_at` or any other mechanism
  enforces absolute session expiry beyond Flask-Login's defaults — assume
  none exists unless A2/unit 13 finds one.
- **Logout**: `app/auth/routes.py:52-58`. `@login_required` (so an
  unauthenticated `POST /logout` 302s to login rather than erroring),
  pops `session["active_module"]`, calls `logout_user()`. No server-side
  session/token revocation list exists — logout relies entirely on
  Flask-Login clearing the client-side session cookie's user-id claim;
  since this is a stateless signed-cookie session (not a server-side session
  store), there is no way to invalidate a session early from the server
  side (e.g. force-logout-all-devices is not implemented anywhere in this
  scope, and no `PASSWORD_CHANGED`-style token invalidation was found —
  `change_password` at `app/auth/routes.py:61-75` does **not** call
  `logout_user()`/rotate any session token after a password change, so
  other already-logged-in sessions for that user, if any existed on other
  devices, would remain valid after a password change). Not verified
  whether this matters in practice (this app has no multi-device concurrent
  session feature visible in scope) — flagging as a gap to note, not a
  confirmed exploitable finding.
- **Open-redirect protection on login**: `_safe_next_url()`
  (`app/auth/routes.py:78-87`) explicitly rejects any `next` value with a
  scheme or netloc, or that doesn't start with `/` — **CONFIRMED safe**
  against the classic `?next=https://evil.example` login-redirect attack.

---

## 4. Authorization primitives — the three-layer model

1. **Module gates** — functions in `app/auth/permissions.py`:
   `can_access_reports_module` (:53-57), `can_access_partners_module`
   (:65-67), `can_access_project_documents_module` (:73-77),
   `can_access_company_media_module` (delegates to
   `app.company_media.permissions.access`). Enforced as shown in §2 — a mix
   of the global hook and per-blueprint `before_request`.
2. **Global roles + DB-backed RBAC** — `UserRole` enum values `SUPER_ADMIN`,
   `ADMIN`, `VIEWER_ADMIN` (legacy `PROJECT_MANAGER`/`REPORTER` not
   re-verified here, models are A2 scope). Permission catalogue:
   `app/permissions/registry.py` — `PERMISSIONS` (a Python list, :40-96),
   `SYSTEM_ROLES` (:8-12), `DEFAULTS` (:98-112, per-role default grant sets
   for `ADMIN` and `VIEWER_ADMIN`; `SUPER_ADMIN`'s entry is
   **`set()` — explicitly empty**, with the comment `# bypass; grants
   intentionally meaningless`, :111). Database sync: `sync_registry()`
   (`app/permissions/sync.py:5-37`) — creates/updates `Role`/`Permission`
   rows and, only if `apply_defaults`/`reset_defaults` is passed, grants
   `RolePermission` rows from `DEFAULTS`. **Never called automatically** —
   confirmed by reading `app/__init__.py` in full, no call to
   `sync_registry`/`register_cli`'s `sync-permissions` command happens at
   app-factory time; it is exposed only as `flask sync-permissions`
   (`app/cli.py`, out of this unit's scope, cited from the CLI command
   registration visible via `register_cli(app)` at `app/__init__.py:83`,
   not re-read here).
   Enforcement primitive: `user_has_permission(user, code)`
   (`app/permissions/services.py:14-28`):
   ```python
   def user_has_permission(user, code):
       if not user or not getattr(user, "is_authenticated", False) or not user.is_active:
           return False
       if user.has_role(UserRole.SUPER_ADMIN.value):
           return True
       cache = getattr(g, "_permission_codes", None)
       ...
       return code in cache
   ```
   (`app/permissions/services.py:14-19`, abbreviated). **CONFIRMED: `SUPER_ADMIN`
   bypasses every single permission code unconditionally**, before the
   per-request `g`-cached permission-code lookup even runs — this is a
   code-level bypass, not a database grant, so **no `RolePermission` row
   exists or is needed for `SUPER_ADMIN`**, and `DEFAULTS[SUPER_ADMIN]`
   being empty is correct/intentional, not a misconfiguration. Unknown
   permission codes are denied and logged (`app/permissions/services.py:26-27`,
   `logger.warning("Unknown permission requested: %s", code)`) — a
   fail-closed behavior for typos in permission codes, confirmed by reading
   the function in full.
   `permission_required(code)` decorator (`app/permissions/services.py:31-38`)
   wraps `user_has_permission` for route use; `any_permission_required`/
   `all_permissions_required` (:40-46) exist as OR/AND variants — **did not
   find any call site for either of these two** in this scope's files (they
   may be called from route files outside A1's scope; not checked here).
3. **Per-project capability flags** — `app/project_memberships.py`, in full:
   `CAPABILITY_FIELDS` (16 boolean flags, :8-14), `PROJECT_ROLE_PRESETS`
   (:34-41) mapping named presets to capability subsets, `has_global_project_scope`
   (:50-57, gated by permission code `"projects.scope_all"`, explicitly
   commented as "a scope permission, not a mutation capability" so it only
   ever grants read-shaped access — confirmed by its only caller-site usage
   inside `user_has_project_capability` being conditioned on
   `capability in READ_CAPABILITIES`, :86), `user_has_project_capability`
   (:78-89, the core check, quoted in full):
   ```python
   def user_has_project_capability(user, project_id, capability):
       if capability not in CAPABILITY_FIELDS:
           return False
       if is_project_admin(user):
           return True
       if is_viewer_admin(user):
           return capability in READ_CAPABILITIES
       if capability in READ_CAPABILITIES and has_global_project_scope(user):
           return True
       membership = active_membership(user, project_id)
       return bool(membership and getattr(membership, capability, False))
   ```
   **CONFIRMED**: an unrecognized capability string is denied outright
   (line 1) — fail-closed against typos here too. `is_project_admin`/
   `is_viewer_admin` (imported, not re-defined in this file — did not chase
   their definitions in this pass, they're referenced as already-established
   from the earlier architecture pass; treat that specific claim as
   **not re-verified in this A1 pass** if precision matters downstream).
   `has_any_project_capability` (:92-100) and `accessible_project_ids`
   (:103+) are OR-across-capabilities / listing helpers used by module-gate
   functions (`can_access_reports_module`, `can_access_project_documents_module`)
   to answer "does this user have *any* project granting them entry to this
   module at all," separately from "can they act on *this specific*
   project" — two different questions, both real and both necessary,
   confirmed by reading both call sites in `app/auth/permissions.py`.
4. **Decorator layer that exists but has (almost) no real callers**:
   `role_required`/`viewer_or_admin_required`/`admin_read_required`/
   `super_admin_required` (`app/auth/permissions.py:15-35`),
   `project_read_required`/`project_write_required`/`project_manage_required`
   (`app/auth/permissions.py:225-249`), and the "compatibility adapter"
   functions `can_write_project`/`can_manage_project`/
   `can_delete_report_for_project`/`can_delete_issue_for_project`/
   `can_manage_persistent_issues` (`app/auth/permissions.py`, various lines
   in the 195-224 range). **Re-confirmed in this pass** (not just carried
   forward from PRE-002): grepping every file actually in scope for this
   unit plus every route file across the repo (as already established
   before this pass) still shows zero real-route call sites for the first
   group and exactly one synthetic-test call site each for
   `project_read_required`/`project_write_required`
   (`tests/conftest.py:30-38`, outside this unit's scope, cited only as
   already-known context). This is a primitive that exists, is exercised by
   its own decorator logic correctly (a decorator test proves the
   decorator works), but **is not load-bearing for any real route in this
   application**.

---

## 5. Input validation

**No global validation layer exists.** Confirmed by reading every file in
scope: there is no `@app.before_request` that runs a schema/shape check
against `request.json`/`request.form` for all routes, no global
Marshmallow/Pydantic/Cerberus integration (none of those packages appear in
`requirements.txt`, and none are imported anywhere in this scope's files).
What exists instead, per-route/per-form:

- **Flask-WTF forms** (`LoginForm`, `ChangePasswordForm`,
  `app/auth/forms.py`) — WTForms validators (`DataRequired`, `Length`,
  `EqualTo`) plus a custom `validate_new_password` (:24-27) that calls
  `password_policy_errors()` (`app/security.py`, in scope). These only
  cover the two HTML-form routes in `app/auth/routes.py`. CSRF validation
  is bundled into `form.validate_on_submit()` automatically via
  Flask-WTF's global `CSRFProtect` (`app/extensions.py:11`,
  `csrf.init_app(app)` at `app/__init__.py:58`) — **CONFIRMED: CSRF
  protection is global and applies to every state-changing endpoint by
  default**, since `CSRFProtect.init_app` hooks all non-GET/HEAD/OPTIONS
  requests app-wide, not per-form; the two `FlaskForm` subclasses here get
  it "for free" as a side effect of being `FlaskForm`s, but plain
  `request.form`-reading routes elsewhere in the app (outside this scope)
  are still covered by the same global CSRF hook, not by these two forms.
- **JSON API routes** (e.g. `daily_report_create_v2`, out of this unit's
  scope but referenced in §2) do their own manual `request.get_json(...)`
  parsing and ad-hoc validation functions, not WTForms, not a shared schema
  layer.
- **Conclusion**: validation coverage is **route-by-route and inconsistent
  in mechanism** (WTForms in two places, hand-written checks everywhere
  else) but CSRF specifically is the one thing that is genuinely global.

---

## 6. Error handling

- **No global `@app.errorhandler(500)` or `@app.errorhandler(Exception)`**
  anywhere in this scope (confirmed, full read of `app/__init__.py`, the
  only registered file capable of defining one at this level). The single
  registered handler is `RequestEntityTooLarge` → 413 (§1, item 5).
- **What happens on an unhandled exception**: standard Flask/Werkzeug
  behavior applies. `Config.DEBUG` (`app/config.py`, in scope) is computed
  as `os.getenv("FLASK_DEBUG", "false").lower() == "true" and APP_ENV !=
  "production"` — **CONFIRMED: `DEBUG` can never be `True` when
  `APP_ENV == "production"`, regardless of what `FLASK_DEBUG` is set to**,
  because of the `and APP_ENV != "production"` clause. With `DEBUG=False`,
  Flask returns a generic "500 Internal Server Error" page with **no
  traceback, no exception message, no source snippet** exposed to the
  client — this is Werkzeug's own safe default, not something this app
  had to build.
- **Does it log anything**: Flask's own default unhandled-exception
  handling logs the exception via the app's logger at ERROR level
  (Flask/Werkzeug built-in behavior, not a statement this codebase wrote
  itself) — no custom logging was added on top of that default in this
  scope, and no custom handler suppresses it either.
- **Flask-Limiter storage-unreachable case** (explicitly asked for in §7,
  answered here since it's error-handling behavior): `Limiter(key_func=
  get_remote_address, default_limits=[])` (`app/extensions.py:12`) — no
  `swallow_errors` argument passed, and `RATELIMIT_SWALLOW_ERRORS` is never
  set in `Config` or the `app.config.setdefault(...)` block
  (`app/__init__.py:14-43`). Read Flask-Limiter's own source
  (`.venv/lib/python3.10/site-packages/flask_limiter/extension.py:318-319`):
  `self._swallow_errors = bool(config.get(ConfigVars.SWALLOW_ERRORS,
  False))` — **default is `False`**. At the actual rate-check call sites
  (e.g. `extension.py:890`), the behavior when not swallowing is `raise err`
  — no log line is emitted by Flask-Limiter itself in the non-swallow
  branch (only the swallow branch calls `self.logger.exception(...)`,
  `extension.py:889`). **CONFIRMED: if `RATELIMIT_STORAGE_URI` (Redis) is
  unreachable, a request to any route carrying an explicit
  `@limiter.limit(...)` decorator will raise an exception that propagates
  up to Flask's default unhandled-exception handling — i.e., it fails
  closed with a generic 500, not open, and not silently.** This only
  affects the specific routes decorated with `@limiter.limit(...)`
  (`default_limits=[]` means there is no app-wide implicit limit applied to
  every route) — routes without that decorator are entirely unaffected by a
  rate-limit-storage outage.

---

## 7. Config & secrets loading

- **Where env vars are read**: `app/config.py`'s `Config` class (module-level
  class attributes, evaluated once at import time) plus
  `app.config.setdefault(...)` in `app/__init__.py:14-43` (infra defaults —
  storage limits, Celery queues, upload/download quotas). `read_secret()`
  (`app/config.py`) prefers `<NAME>_FILE` (Docker secret file path) over the
  plain env var of the same name, raising `RuntimeError` if the file path is
  set but unreadable or empty — **CONFIRMED fail-closed for the
  `_FILE`-secret path specifically** (a misconfigured secret mount crashes
  startup rather than silently falling back to a default).
- **Boot-time validation**: `production_configuration_errors()`
  (`app/security.py`, in scope, called at `app/__init__.py:46-48`) — **but
  only when `config.get("APP_ENV") == "production"`** (`app/security.py`,
  `production_configuration_errors`'s first line: `if config.get("APP_ENV")
  != "production": return []`). In non-production `APP_ENV` values (`local`,
  unset, or anything else a typo could produce), **zero boot-time config
  validation runs** — a deployment that forgets to set `APP_ENV=production`
  would silently skip every one of these checks (default secret key,
  sample database URL, `DEBUG` on, missing secure/httponly cookie flags,
  `STORAGE_PROVIDER=fake` in what's actually a real deployment). This is a
  real, confirmed gap in the *validation trigger itself*, not just in a
  particular check — flagging for Unit 12/1 to consider: is `APP_ENV`
  itself validated against a fixed set of allowed values anywhere? **Not
  found in this scope** — `APP_ENV` is read as a free string
  (`app/config.py`, `os.getenv("APP_ENV", "local")`) with no enum/allow-list
  check.
- **`RATELIMIT_STORAGE_URI` default**: `"redis://127.0.0.1:6379/2"` in
  `Config` (`app/config.py`), separately defaulted again to `"memory://"`
  via `app.config.setdefault("RATELIMIT_STORAGE_URI", "memory://")`
  (`app/__init__.py:14`). **These two defaults disagree** — if
  `Config.RATELIMIT_STORAGE_URI` is always a concrete string (never `None`,
  since `os.getenv(..., "redis://127.0.0.1:6379/2")` always returns
  something), the `app.config.setdefault(...)` call at `app/__init__.py:14`
  is **dead code for this specific key** — `setdefault` only takes effect
  if the key is absent, and `Config.RATELIMIT_STORAGE_URI` always sets it.
  Not a security finding, but worth flagging as a maintenance trap: the
  `"memory://"` fallback documented/implied at the `app/__init__.py` level
  can never actually apply while `Config` is the active config class,
  because `Config` always wins first. (`TestConfig` in `tests/conftest.py`,
  out of scope, does not set this key at all, so tests *do* fall through to
  whichever of the two defaults actually applies — not re-verified here.)
- **Boot-time production validation, quoted in full** (`app/security.py`,
  read fully in this pass; cited here rather than re-pasted at length,
  matches `ARCHITECTURE.md`'s §Configuration section — that prior read is
  re-confirmed, not contradicted, by this pass): checks `SECRET_KEY` default/
  short, sample/SQLite `DATABASE_URL`, `DEBUG` on, `SESSION_COOKIE_SECURE`/
  `HTTPONLY`/`SAMESITE`, `STORAGE_PROVIDER == "fake"`, and S3 credential
  presence when `STORAGE_PROVIDER == "s3"`. **Does not check**
  `RATELIMIT_STORAGE_URI` (a `memory://` limiter in a multi-worker
  production Gunicorn deployment silently under-enforces rate limits per
  PRE-003's multiplier finding — `security-audit`'s CLI command, out of this
  unit's scope, does separately check `RATELIMIT_STORAGE_URI` starts with
  `redis://`/`rediss://` per the earlier architecture pass, but
  `production_configuration_errors()` itself, which is what actually blocks
  *startup*, does not).

---

## 8. Logging — tokens/passwords/PII

- **Passwords**: never logged in this scope. `log_audit("auth.login_failed",
  ...)` (`app/auth/routes.py:35`) logs the attempted `login_value`
  (username/email) but explicitly not `form.password.data` — confirmed by
  reading the full call, only `new_values={"login": login_value}` is
  passed.
- **Secrets**: `read_secret()` (`app/config.py`) reads but never logs
  `SECRET_KEY`/`STORAGE_ACCESS_KEY_ID`/`STORAGE_SECRET_ACCESS_KEY` — no
  `print`/`logger`/`click.echo` call touches the returned value anywhere in
  this scope's files.
- **`app/celery_app.py`'s worker-identity log line** (:40-47) logs
  `flask_app.config["APP_ENV"]`, database name, db user, migration revision,
  `STORAGE_PROVIDER`, `STORAGE_BUCKET`, and `broker.hostname` (parsed via
  `urlparse`, **hostname only, not the full broker URL** — so any
  credentials embedded in `CELERY_BROKER_URL` as `redis://user:pass@host`
  are **not** logged, only `host`, confirmed by reading `urlparse(...).hostname`
  usage at line 39/45). This is a good pattern, worth noting as a
  guarantee-adjacent positive rather than a gap.
- **PII**: nothing in this scope's files logs user PII (email/full name)
  directly — the only user-supplied string that reaches a log call at all
  in this unit's scope is the failed-login `login_value`, which is written
  to the `AuditLog` table (a DB row, not an application log stream) rather
  than to `app.logger`/stdout.

---

## GUARANTEES

Module auditors in Batch 1+ may assume, without re-deriving:

- Every request to every registered endpoint (except `auth.login`, `health`,
  `healthz`, `static`, and endpoint-less 404s) requires an authenticated
  session — enforced once, globally, in `require_login`
  (`app/__init__.py:155-167`), and cannot be bypassed per-blueprint.
- CSRF protection is global (`CSRFProtect`, `app/extensions.py:11`) and
  applies to every state-changing request by default, independent of
  whether the route uses a `FlaskForm`.
- `SUPER_ADMIN` bypasses every RBAC permission code unconditionally, in code
  (`app/permissions/services.py:16-17`), not via database grants — no
  `RolePermission` row is required or expected for this role.
- An unrecognized permission code or an unrecognized per-project capability
  string is denied by default (fail-closed), not silently ignored —
  confirmed in both `user_has_permission` and `user_has_project_capability`.
- The login `next` redirect parameter cannot be used for an open redirect
  (`_safe_next_url()`, `app/auth/routes.py:78-87`).
- In production (`DEBUG=False`, which is unconditionally forced whenever
  `APP_ENV=="production"`), an unhandled exception never leaks a traceback
  or exception message to the client — generic 500 only.
- Partner-suite blueprints (`partners`, `partner_companies`, `partner_fields`,
  `partner_field_collections`, `partner_relations`), `project_documents`,
  and `company_media` each independently enforce their own module gate via
  `@bp.before_request` — this does not depend on the global hook's prefix
  tuple at all, and is confirmed present in all 7.
- **Nothing in this unit's scope logs a session cookie, a CSRF token, a
  password, or a full request body.** Confirmed by grepping every file in
  scope for `request.cookies`, `csrf_token`, `request.get_data`,
  `request.data`, and by reading the three password-touching code paths in
  full: `login()` logs only the attempted username/email on failure, never
  the password (`app/auth/routes.py:34-38`); `change_password()` never logs
  either password (`app/auth/routes.py:63-75`); there is **no
  password-reset flow in this codebase at all** (`app/auth/routes.py` has
  exactly three routes — login, logout, change-password — confirmed by
  reading the full 93-line file; no reset-token generation/storage/logging
  exists to leak in the first place). `app/celery_app.py`'s worker-identity
  log line (:40-47) parses `CELERY_BROKER_URL` with `urlparse(...).hostname`
  specifically so embedded credentials never reach the log
  (`app/celery_app.py:39,45`).
- **`app/security.py` registers no middleware itself** — it is a pure
  helper-function module (`storage_connect_source`, `password_policy_errors`/
  `validate_password`, `is_default_secret_key`,
  `is_unsafe_production_database_url`, `production_configuration_errors`;
  `app/security.py:10-83` in full). Every protection it enables is only as
  strong as its one caller: `storage_connect_source()` is consumed by
  `add_security_headers` (`app/__init__.py:210-220`) to widen the CSP;
  `production_configuration_errors()` is consumed once, at
  `app/__init__.py:46-48`, gated entirely on `APP_ENV=="production"` (see
  NOT GUARANTEED and A1-001 in `PRE-FINDINGS.md`); `password_policy_errors`/
  `validate_password` are consumed by `ChangePasswordForm`
  (`app/auth/forms.py:24-27`) and, outside this unit's scope, by
  `flask seed-admin`. `security.py` itself performs **no host validation**
  — that is `require_trusted_host` in `app/__init__.py` (§1), a different
  file, already covered above.

## NOT GUARANTEED — every unit must check these per-endpoint itself

- **`daily_report_create_v2` has no module-level gate** (only a per-project
  capability check) — unit 3b must determine whether this matters given the
  narrow theoretical gap described in PRE-011, and must not assume the
  global hook or a blueprint `before_request` protects any route in
  `app/reports/create_v2.py`.
- **The global module-gate hook only covers 8 blueprint-name prefixes plus
  11 named `admin.*` endpoints** — any blueprint not in §2's "global hook"
  or "own before_request" rows has **no module gate at all**, by design
  (RBAC-only or pre-login surfaces) — but a *new* route added to one of
  those blueprints in the future would silently inherit that same
  no-module-gate status; each unit auditing `admin`/`admin_storage`/`users`
  must confirm every individual route has its own `@permission_required(...)`
  or equivalent, since there is no module-level backstop for these three.
- **Per-project capability checks (`can_edit_report`, `can_view_issue`,
  etc.) are called inline, per-route, with no shared decorator** (§4, item
  4) — every route in every unit must be individually confirmed to call the
  right capability check with the right project/object ID; nothing here
  guarantees consistency across routes.
- **RBAC's DB-backed grants are never auto-synced** — a fresh environment
  or a permission-registry change that hasn't had `flask sync-permissions`
  run against it will have stale/missing `RolePermission` rows; this
  doesn't fail closed automatically at the app level (no boot-time check
  compares `registry.py`'s `PERMISSIONS`/`DEFAULTS` against the live DB
  rows) — if a later unit's tests pass against a freshly-`db.create_all()`d
  test database (as `tests/conftest.py` does, calling `sync_registry` in
  its fixture — noted, not re-verified in this A1 pass since conftest is
  out of scope), that does not prove the same holds in a real deployment
  that skipped the sync step.
- **`SESSION_COOKIE_SECURE`/`SECRET_KEY`-default/sample-database-URL/`DEBUG`-
  on/`STORAGE_PROVIDER=fake`-and-S3-credential hard startup failures are
  entirely conditional on `APP_ENV` being the exact string `"production"`
  — moved here from GUARANTEES in this addendum, see **A1-001** below and in
  `PRE-FINDINGS.md` for the full analysis.** No validation of `APP_ENV`
  itself against an allow-list exists anywhere in this scope; a typo'd,
  unset, or otherwise-misspelled `APP_ENV` silently skips all 8 checks in
  `production_configuration_errors()` (`app/security.py:61-83`).
  Downstream units must not assume "the app started successfully" implies
  "the production config checks ran and passed" — it only implies that if
  `APP_ENV` happened to be spelled exactly right.
- **CSRF covers state-changing *browser form* submissions; it does not by
  itself validate JSON-API request bodies' business logic** — each JSON API
  route (e.g. `daily_report_create_v2`, `project_documents`'s
  presign/complete endpoints, out of this unit's scope) must be checked
  individually for its own payload validation; there is no shared schema
  layer to lean on (§5).
- **Session expiry relies entirely on Flask-Login's defaults**; no absolute
  session lifetime, no forced re-authentication after a password change
  (`change_password` does not call `logout_user()` or rotate anything, §3)
  — units touching account security/session handling must not assume a
  password change invalidates other active sessions.
- **`RATELIMIT_STORAGE_URI`'s two conflicting defaults** (`Config`'s
  `redis://127.0.0.1:6379/2` vs. `app/__init__.py`'s dead-code
  `"memory://"` `setdefault`) mean the *actual* effective default in any
  given environment depends on exactly which config class is active and
  whether `RATELIMIT_STORAGE_URI` is set in the environment — do not assume
  either documented default without checking the live environment. **See
  the A1 ADDENDUM below for the resolved answer on what happens when that
  storage is unreachable — it is no longer an open question, but the
  specific limits/endpoints affected still need per-unit awareness.**
- **The role predicates this pass could not read must not be assumed to
  behave as their names suggest.** `is_project_admin(user)` and
  `is_viewer_admin(user)` are imported into and used throughout
  `app/project_memberships.py` (e.g. `user_has_project_capability`, §4) but
  are **not defined in any file in this unit's scope** — this pass read
  `app/project_memberships.py` in full and can confirm *how* these
  predicates are used (their boolean results gate admin-bypass and
  viewer-admin read-only behavior) but **not what they actually check**
  (which role code(s), whether they consult `User.role_id` vs the legacy
  `role`/`legacy_role` column, whether they're affected by `is_active`,
  etc.). The same applies to `app/models/user.py`'s `role_code`/`has_role`/
  `can` methods, referenced in §4 but not re-read line-by-line in this A1
  pass — those claims are carried from an earlier architecture pass, not
  fresh in this document. **This is explicitly Foundation-A2's
  responsibility to close** (`app/models/` is in A2's scope): A2 must quote
  `is_project_admin`/`is_viewer_admin`'s actual definitions (wherever they
  live — not yet located) and confirm or correct every claim in this
  document's §4 that depends on them. Until A2 does that, no Batch-1+ unit
  should treat "admin bypass" or "viewer-admin is read-only" as verified
  beyond the specific `READ_CAPABILITIES` set/`CAPABILITY_FIELDS` check
  already quoted in §4 of this document.
- **This pass did not read** `app/models/user.py` (beyond the one method
  signature carried from the earlier architecture pass), `tests/conftest.py`,
  or `app/cli.py`. Treat anything in this document attributed to those
  files as "consistent with the prior pass," not as freshly re-confirmed
  here.

---

# A1 ADDENDUM — corrections and gaps closed

Written after review. Does not replace anything above except where noted;
GUARANTEES/NOT GUARANTEED have already been edited in place (one bullet
moved, several added) — this section is the evidence trail for those edits
plus the two items that needed new investigation.

## A1-001 — Production config validation is conditional on an unvalidated `APP_ENV` string

**Finding, elevated from a caveat to a numbered finding.** File:line:
`app/security.py:62`:

```python
def production_configuration_errors(config) -> list[str]:
    if config.get("APP_ENV") != "production":
        return []
```

The exact string comparison is `config.get("APP_ENV") != "production"` — a
plain Python string inequality against the single literal `"production"`.
`APP_ENV` itself is read at `app/config.py` as `os.getenv("APP_ENV",
"local")` — a free-form string with no enum/allow-list validation anywhere
in this scope (confirmed by reading `app/config.py` in full: no
`if APP_ENV not in {...}` check exists).

**Full list of checks skipped when `APP_ENV` is absent, `"local"`, or
misspelled** (e.g. `"Production"`, `"prod"`, `"PRODUCTION"`, a trailing
space from a copy-pasted `.env` line) — all inside
`production_configuration_errors()`, `app/security.py:61-83`:

1. `SECRET_KEY` missing/default/too short (`:66-67`, via `is_default_secret_key`, `:46-48`)
2. `DATABASE_URL` missing/sample/SQLite (`:68-69`, via `is_unsafe_production_database_url`, `:51-58`)
3. `DEBUG` enabled (`:70-71`)
4. `SESSION_COOKIE_SECURE` disabled (`:72-73`)
5. `SESSION_COOKIE_HTTPONLY` disabled (`:74-75`)
6. `SESSION_COOKIE_SAMESITE` not `Lax`/`Strict` (`:76-77`)
7. `STORAGE_PROVIDER == "fake"` (`:78-80`)
8. `STORAGE_PROVIDER == "s3"` with missing bucket/credentials (`:81-82`)

**Concrete consequence at deploy time**: this function's return value is
the *only* thing standing between a misconfigured production deployment and
a silent `RuntimeError` never being raised — the caller,
`app/__init__.py:46-48`, is unconditional:

```python
configuration_errors = production_configuration_errors(app.config)
if configuration_errors:
    raise RuntimeError("Unsafe production configuration: " + "; ".join(configuration_errors))
```

If an operator's `.env`/Docker secret/Compose environment block sets every
other production value correctly but sets `APP_ENV=Production` (capital P,
a plausible human typo) or omits `APP_ENV` entirely (defaulting to
`"local"`), **the app starts successfully with a default/weak `SECRET_KEY`,
`SESSION_COOKIE_SECURE=False`, and/or `STORAGE_PROVIDER=fake` and gives no
indication anything is wrong** — no log line, no warning, no non-zero exit
code. This is a single-string-comparison gate for the entire production
safety net.

**Minimal fix (not implemented — read-only pass)**: validate `APP_ENV`
against a fixed allow-list (e.g. `{"local", "test", "staging",
"production"}`) at the same point `production_configuration_errors()` is
called, and fail closed (raise, don't default) on any value outside that
set — so a typo produces an immediate, loud startup failure instead of a
silent pass-through to `"local"`-shaped behavior. Recorded in
`PRE-FINDINGS.md` as a Phase 11 blocker candidate; not fixed here per the
read-only/audit-only rule for this branch.

## Rate-limit storage unreachable — resolved, not just re-described

**Answer: (iii) raises — per request, not at startup.** Determined by
reading `flask_limiter`'s actual installed source
(`.venv/lib/python3.10/site-packages/flask_limiter/extension.py`), not just
this app's config, since the app's own config alone (as noted in the
original §6/§7) only tells you the *inputs*, not Flask-Limiter's decision
tree over those inputs.

**Storage connection timing — lazy, not eager.** `Limiter.init_app()`
(`extension.py:292-345`) calls `storage_from_string(...)` synchronously at
Flask app-factory time (`limiter.init_app(app)`, `app/__init__.py:59`), but
this only *constructs* a storage client object — for the Redis backend
(`limits/storage/redis.py:67-141`), the constructor calls
`self.get_connection().register_script(...)` several times (`redis.py:124-139`),
and `register_script` on a redis-py client is a **local, no-network-round-trip
operation** (it does not call `.ping()` or any other command against the
server — no `ping()` call exists in `RedisStorage.__init__`, confirmed by
reading the full constructor). **No network connection to Redis is
attempted at app startup.** The first real network round-trip happens on
the first actual rate-limit check (a `GET`/`INCR`-shaped command inside
`Limiter.hit()`/`Limiter.test()`), which only happens when a request hits a
route carrying an explicit `@limiter.limit(...)` decorator (see below for
which routes) or the (unused, `default_limits=[]`) global default. **A
completely unreachable `RATELIMIT_STORAGE_URI` will not prevent the app
from starting** — it will only surface on the first request to a
rate-limited route.

**What happens on that first request**, traced through
`_check_request_limit` (`extension.py:1146-1173`):

```python
def _check_request_limit(self, callable_name=None, in_middleware=True):
    endpoint = self.identify_request()
    try:
        all_limits = self.__filter_limits(endpoint, flask.request.blueprint, callable_name, in_middleware)
        self.__evaluate_limits(endpoint, all_limits)
    except Exception as e:
        if isinstance(e, RateLimitExceeded):
            raise e
        if self._in_memory_fallback_enabled and not self._storage_dead:
            self.logger.warning("Rate limit storage unreachable - falling back to in-memory storage")
            ...
        else:
            if self._swallow_errors:
                self.logger.exception("Failed to rate limit. Swallowing error")
            else:
                raise e
```

Three config values decide which branch this app takes, **all three
confirmed unset anywhere in `app/config.py` or the `app.config.setdefault(...)`
block** (`app/__init__.py:14-43`), by grep — so all three are at
Flask-Limiter's own library defaults:

| Config var | This app's value | Library default | Source |
|---|---|---|---|
| `RATELIMIT_SWALLOW_ERRORS` | unset → `False` | `False` | `extension.py:318-319` |
| `RATELIMIT_IN_MEMORY_FALLBACK_ENABLED` | unset → `False` | `False` | `extension.py:756` |
| `RATELIMIT_IN_MEMORY_FALLBACK` (limit strings) | unset → `[]` | none | `extension.py:757-760` (also empty since `in_memory_fallback` wasn't passed to the `Limiter(...)` constructor in `app/extensions.py:12` either) |

With `_in_memory_fallback_enabled=False`, the middle branch is skipped
entirely — **this app's Flask-Limiter never falls back to in-memory
storage under any condition**, and with `_swallow_errors=False`, the final
`else` branch is `raise e` with **no log statement at all** (the
`self.logger.exception(...)` call only exists in the swallow-errors branch,
which this app never takes). **CONFIRMED: this app fails closed (raises)
per request, and Flask-Limiter itself logs nothing when it does — the only
logging that occurs is whatever Flask's own default unhandled-exception
handling produces once the exception propagates past Flask-Limiter (§6).**
This corrects the original document's §6, which had already reached the
same raises-not-swallows conclusion but had not yet traced the
in-memory-fallback branch or the eager-vs-lazy connection question.

**Blast radius — every route carrying an explicit `@limiter.limit(...)`**
(there is no app-wide default limit; `Limiter(key_func=get_remote_address,
default_limits=[])`, `app/extensions.py:12`, `default_limits=[]` is empty,
confirmed). Undecorated routes still pass through the global
`_check_request_limit` before_request hook (registered unconditionally,
`extension.py:469`, since `_auto_check` defaults `True` and is never
overridden here) but evaluate against zero limits and never touch storage
at all — **a storage outage cannot affect any route without an explicit
`@limiter.limit(...)` decorator**. The full list of decorated routes found
across the codebase (cross-referencing `ARCHITECTURE.md`'s route inventory,
not re-derived from scratch in this addendum):

| Route | Limit | Configured via |
|---|---|---|
| `POST auth.login` | `RATELIMIT_LOGIN_LIMIT`, default `"5 per minute"` | `app/auth/routes.py:19`, config-driven |
| `GET admin_storage.export_csv` | `RATELIMIT_EXPORT_LIMIT`, default `"10 per hour"` | `app/admin_storage/routes.py`, config-driven |
| `POST projects.report_upload_session_create` | `"30 per minute"` | `app/projects/routes.py:136`, hardcoded |
| `POST projects.report_upload_session_presign` | `"60 per minute"` | `app/projects/routes.py:157`, hardcoded |
| `POST projects.report_upload_session_complete` | `"120 per minute"` | `app/projects/routes.py:167`, hardcoded |
| `POST daily_report_create_v2.create_session` | `"30 per minute"` | `app/reports/create_v2.py:51`, hardcoded |
| `POST daily_report_create_v2.preflight` | `"30 per minute"` | `app/reports/create_v2.py:65`, hardcoded |
| `POST daily_report_create_v2.presign` | `"60 per minute"` | `app/reports/create_v2.py:95`, hardcoded |
| `POST daily_report_create_v2.complete` | `"120 per minute"` | `app/reports/create_v2.py:105`, hardcoded |
| `POST daily_report_create_v2.finalize` | `"20 per minute"` | `app/reports/create_v2.py:129`, hardcoded |

Practical reading: a Redis outage does not silently open the floodgates
(concern (i), ruled out) and does not quietly degrade to a
weaker-but-functioning in-memory limiter (concern (ii), ruled out because
this app never enables that feature) — it turns login, CSV export, and
every daily-report upload-session endpoint (both v1 and v2 flows) into a
generic 500 for every request, until Redis is reachable again. That is a
genuine availability risk (a Redis blip takes down report submission
entirely) but not a security-bypass risk (nothing becomes *less* protected
during the outage — the affected routes fail closed, not open).
