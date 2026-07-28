# Verified Critical Findings

| ID | Original severity | Verdict | Adjusted severity | Minimum attacker | Reason |
|---|---|---|---|---|---|
| 01 | CRITICAL | CONFIRMED | CRITICAL | Active user with `users.view` and `users.manage` (the default `ADMIN` has both) | The edit handler accepts any existing `role_id`, including `SUPER_ADMIN`, for the caller's own account. |
| 02 | CRITICAL | CONFIRMED | CRITICAL | Active user with `users.manage` (the default `ADMIN`) | The reset handler permits any target role, replaces the target hash, commits, and flashes the new plaintext password. |
| 03 | CRITICAL | CONFIRMED | CRITICAL | Active user with both `roles.view` and `roles.manage` | A role manager can rewrite their own non-`SUPER_ADMIN` role and add arbitrary registry permissions; this can be chained to full role takeover. |
| 04 | CRITICAL | CONFIRMED | CRITICAL | Active user with `project_assignments.manage` only | The registered membership-create endpoint accepts self as target and all 17 capability flags for any project, without a project/target/grant-subset check. |
| 05 | CRITICAL | CONFIRMED | HIGH | Active non-viewer user with only a matching active album ACL containing `can_share` | `can_share` reaches ACL management, which overwrites that same ACL with edit/delete/upload/download; impact is limited to the album rather than system-wide. |

## 01 — ADMIN self-grants SUPER_ADMIN through user edit

- Verdict: **CONFIRMED**
- Adjusted severity: **CRITICAL**
- Reachability: `admin.users_edit` is registered as `GET, POST /admin/users/<int:user_id>/edit` (verified with `flask --app run.py routes`). The `admin` blueprint is mounted at `/admin` in `app/admin/__init__.py:3` and registered in `app/__init__.py:112`.
- Code actually read: `app/__init__.py:152-189`; `app/admin/__init__.py:1-5`; `app/admin/routes.py:58-70,441-504,627-674`; `app/permissions/services.py:14-38`; `app/models/user.py:8-31,77-87`; `app/models/rbac.py:7-44`; `app/permissions/registry.py:49-55,98-111`.
- Upward guard trace:
  1. The app-wide hook redirects unauthenticated callers (`app/__init__.py:155-167`); CSRF is globally initialized (`app/__init__.py:58`). Neither prevents an authenticated attacker from sending their own valid form.
  2. No `admin` blueprint `before_request` exists. The reports-module hook does not include this endpoint; its named admin list is only project/category handlers (`app/__init__.py:180-185`).
  3. `@permission_required("users.view")` is the outer route guard (`app/admin/routes.py:58-60`), then POST calls `_require_users_manage()` (`:61-64`, `:627-629`). The actual minimum is therefore both `users.view` and `users.manage`; default `ADMIN` grants both because `DEFAULTS[ADMIN]` excludes neither (`app/permissions/registry.py:98-100`).
  4. No target-user restriction, self-target restriction, or role hierarchy restriction follows.
- Downward mutation trace:
  1. `_save_user` reads `role_id` directly from `request.form` and resolves any `Role` row (`app/admin/routes.py:443-466`).
  2. It calls `ensure_not_last_active_super_admin` only for an existing target, then assigns `user.role`, `user.role_id`, and the compatibility field (`:487-492`).
  3. The helper only rejects the removal/deactivation of the sole active super admin (`:670-674`); a non-super-admin being promoted does not satisfy its condition.
  4. It flushes, records audit metadata, and commits with no rejection/rollback branch (`:494-504`). `User.role_code` subsequently resolves from this persisted relationship (`app/models/user.py:77-82`); `SUPER_ADMIN` then bypasses every RBAC code (`app/permissions/services.py:17-18`).
- Quoted evidence:

  ```python
  role_id = request.form.get("role_id", "").strip()
  role = db.session.get(Role, int(role_id)) if role_id.isdigit() else None
  ```
  `app/admin/routes.py:446-458`

  ```python
  user.role = role
  user.role_id = role.id
  db.session.commit()
  ```
  `app/admin/routes.py:489-502`

  ```python
  if user.has_role(UserRole.SUPER_ADMIN.value) and user.is_active and not will_remain ...:
  ```
  `app/admin/routes.py:670-674`
- Explanation: An ordinary default `ADMIN` can POST their own ID and the existing `SUPER_ADMIN` role ID. The secure PoC observed HTTP 302 and persisted `role_code='SUPER_ADMIN'`; it must instead reject the request and retain `ADMIN`.

## 02 — ADMIN resets a SUPER_ADMIN password and receives the temporary password

- Verdict: **CONFIRMED**
- Adjusted severity: **CRITICAL**
- Reachability: `admin.users_reset_password` is registered as `POST /admin/users/<int:user_id>/reset-password` (verified with `flask --app run.py routes`), under the same mounted and registered `admin` blueprint above.
- Code actually read: `app/__init__.py:152-189`; `app/admin/routes.py:199-208`; `app/admin/services.py:77-83`; `app/permissions/services.py:14-38`; `app/models/user.py:8-31,74-87`; `app/permissions/registry.py:49-55,98-111`.
- Upward guard trace:
  1. Global login and CSRF apply as above. The reports-module hook does not cover `admin.users_reset_password`.
  2. The sole route authorization is `@permission_required("users.manage")` (`app/admin/routes.py:199-201`). Default `ADMIN` has this grant (`app/permissions/registry.py:98-100`).
  3. `db.get_or_404(User, user_id)` proves only that the target exists. There is no role check, no hierarchy check, no self-only check, and no service-layer authorization after the route decorator.
- Downward mutation trace:
  1. `temporary_password()` builds a 14-character value containing all policy groups (`app/admin/services.py:77-80`).
  2. The route hashes it into the arbitrary target's `password_hash`, records an audit event, commits, and includes the plaintext in the flash (`app/admin/routes.py:202-208`).
  3. `User.check_password` uses that stored hash (`app/models/user.py:74-75`), so the disclosed temporary password authenticates as the target.
- Quoted evidence:

  ```python
  password = temporary_password()
  user.password_hash = generate_password_hash(password)
  ```
  `app/admin/routes.py:202-204`

  ```python
  db.session.commit()
  flash(f"Mật khẩu tạm cho {user.username}: {password}", "warning")
  ```
  `app/admin/routes.py:205-208`
- Explanation: A default `ADMIN` can name any active `SUPER_ADMIN` ID. The secure PoC observed a changed target password hash and the Vietnamese temporary-password flash marker in the redirected response. This is a direct privileged-account takeover, not merely a reset-policy weakness.

## 03 — Holder of roles.manage rewrites their own/system-role permissions

- Verdict: **CONFIRMED**
- Adjusted severity: **CRITICAL**
- Reachability: `admin.role_permissions` is registered as `GET, POST /admin/roles/<int:role_id>/permissions` (verified with `flask --app run.py routes`), on the registered `admin` blueprint.
- Code actually read: `app/__init__.py:152-189`; `app/admin/routes.py:142-179`; `app/permissions/services.py:14-38`; `app/models/rbac.py:7-44`; `app/models/user.py:77-87`; `app/permissions/registry.py:40-111`.
- Upward guard trace:
  1. Global authentication/CSRF apply; neither is a target-role constraint for an authenticated caller. This endpoint is not in the reports-module hook's named admin list.
  2. The outer decorator requires `roles.view` (`app/admin/routes.py:142-144`), and the POST branch separately requires `roles.manage` (`:146-148`). Thus the precise minimum is both grants, not `roles.manage` in isolation.
  3. The only target restriction is `role.code == SUPER_ADMIN`; it does not block `ADMIN`, `VIEWER_ADMIN`, or an attacker's own custom role. `Role.is_system` is not consulted here, despite being enforced by the sibling role-name editor (`app/admin/routes.py:123-128`).
- Downward mutation trace:
  1. The request supplies `permission_ids`; numeric IDs are accepted and each existing `Permission` is inserted (`app/admin/routes.py:149-154`). There is no allow-list by target role, no dangerous-permission block, and no requirement the actor already holds a selected permission.
  2. All target `RolePermission` rows are deleted, the selected set is rebuilt, audited, and committed (`:150-157`). `RolePermission` is the join table used by `user_has_permission` to determine a non-super-admin's effective permissions (`app/permissions/services.py:19-29`; `app/models/rbac.py:36-44`).
  3. No rollback/error path protects an authorized POST.
- Quoted evidence:

  ```python
  if not current_user.can("roles.manage") or role.code == UserRole.SUPER_ADMIN.value:
      abort(403)
  ```
  `app/admin/routes.py:146-148`

  ```python
  RolePermission.query.filter_by(role_id=role.id).delete()
  for permission_id in selected:
      if db.session.get(Permission, permission_id):
          db.session.add(RolePermission(role_id=role.id, permission_id=permission_id))
  ```
  `app/admin/routes.py:149-154`
- Explanation: The secure PoC creates a non-system role having only the two required route grants, then submits its own role with `system.settings`. The current route returns 302 and persists that dangerous grant. The same primitive can add `users.view`/`users.manage`, then use finding 01 to obtain `SUPER_ADMIN`; the `SUPER_ADMIN` target exclusion does not stop that chain.

## 04 — Holder of project_assignments.manage inserts themselves into any project with full capabilities

- Verdict: **CONFIRMED**
- Adjusted severity: **CRITICAL**
- Reachability: `admin.memberships_create` is registered as `POST /admin/projects/<int:project_id>/memberships` (verified with `flask --app run.py routes`). The actual endpoint name differs from the reports-module hook's stale `admin.projects_memberships` entry (`app/__init__.py:180-185`), so this handler receives no reports-module gate.
- Code actually read: `app/__init__.py:88-135,152-189`; `app/admin/__init__.py:1-5`; `app/admin/routes.py:284-336`; `app/admin/services.py:24-39`; `app/permissions/services.py:14-38`; `app/project_memberships.py:8-125`; `app/models/project.py:68-118`; `app/permissions/registry.py:49-60,98-111`.
- Upward guard trace:
  1. The global login and CSRF protections apply. No `admin` blueprint hook applies.
  2. The sole effective authorization is `@permission_required("project_assignments.manage")` (`app/admin/routes.py:284-286`). The stale module-hook string is `admin.projects_memberships`, while Flask registers the handler as `admin.memberships_create`.
  3. The route verifies the requested `Project` exists and the requested user exists, is active, and is not soft deleted (`:287-291`). It does not check the actor administers that project, that actor differs from target, or that the actor holds any requested capability.
- Downward mutation trace:
  1. Request fields choose `user_id`, `project_role_code`, and each member of `CAPABILITY_FIELDS` (`app/admin/routes.py:288,326-336`; `app/project_memberships.py:8-15`). `PROJECT_OWNER` is defined as all 17 fields (`app/project_memberships.py:36-43`).
  2. The route finds or constructs the `(project_id, user_id)` membership, flushes a new row, applies every requested flag, sets it active, audits, and commits (`app/admin/routes.py:292-303`). The database unique constraint prevents duplicates but does not restrict the actor or flags (`app/models/project.py:68-115`).
  3. These flags are the authorization source of truth (`app/models/project.py:87-89`); `user_has_project_capability` reads an active membership's named flag (`app/project_memberships.py:78-89`).
- Quoted evidence:

  ```python
  @bp.post("/projects/<int:project_id>/memberships")
  @permission_required("project_assignments.manage")
  ```
  `app/admin/routes.py:284-286`

  ```python
  enabled = {field for field in CAPABILITY_FIELDS if request.form.get(field) == "1"}
  for field in CAPABILITY_FIELDS:
      setattr(membership, field, field in enabled)
  ```
  `app/admin/routes.py:326-336`

  ```python
  "PROJECT_OWNER": set(CAPABILITY_FIELDS),
  ```
  `app/project_memberships.py:36-43`
- Explanation: The secure PoC gives a custom account only `project_assignments.manage`, posts itself to otherwise unrelated project 2 with every flag, and observes HTTP 302 plus a persisted active owner-equivalent membership. No reports-module permission, existing project membership, or granted capability was needed.

## 05 — Company Media can_share ACL holder self-escalates album capabilities

- Verdict: **CONFIRMED**
- Adjusted severity: **HIGH** (was CRITICAL)
- Reachability: `company_media.permissions` is registered as `GET, POST /company-media/albums/<int:album_id>/permissions` (verified with `flask --app run.py routes`), mounted by `app/company_media/__init__.py:1-3` and registered by `app/__init__.py:123-124`.
- Code actually read: `app/__init__.py:88-135,152-189`; `app/company_media/__init__.py:1-3`; `app/company_media/routes.py:14-20,172-197`; `app/company_media/permissions.py:7-82`; `app/company_media/services.py:78-95`; `app/models/company_media.py:8-68`; `app/models/user.py:8-31,77-87`; `app/permissions/services.py:14-38`; `app/templates/company_media/permissions.html:1-36`; `app/static/js/company-media-permissions.js:20-35`.
- Upward guard trace:
  1. Global login/CSRF apply. The blueprint hook calls `p.access(current_user)` (`app/company_media/routes.py:18-20`).
  2. `access()` treats any active matching ACL carrying any of its six flags as module access (`app/company_media/permissions.py:18-41`). Thus `can_share` alone reaches the route without `modules.company_media.access`.
  3. The route then calls `p.share_album(current_user, album, True)` (`app/company_media/routes.py:172-176`). For a non-admin/non-viewer account, `_can` returns true immediately on a matching ACL for the requested action (`app/company_media/permissions.py:55-68`); it does not require the matching user to have RBAC action permissions.
  4. The template states ACL permissions should only supplement matching RBAC (`app/templates/company_media/permissions.html:17`), but the actual `_can` short circuit contradicts that stated policy.
- Downward mutation trace:
  1. The POST accepts arbitrary `principal_type`, `principal_id`, and all six capability controls. It calls `set_permission` without an actor-capability subset check (`app/company_media/routes.py:176-184`).
  2. `set_permission` resolves any valid user/role, requires only one selected flag, finds or creates its ACL, assigns each flag from the request, and commits (`app/company_media/services.py:78-95`). It neither inspects `user` for permission nor records an audit row.
  3. The persisted ACL controls future edit/delete/upload/download decisions through the same `_matching_acl_allows` short circuit (`app/company_media/permissions.py:44-68,73-81`).
- Quoted evidence:

  ```python
  return bool(_active_user(user) and (
      user.role_code in ADMIN_ROLES | {UserRole.VIEWER_ADMIN.value}
      or has_module_access(user)
      or has_album_acl(user)
  ))
  ```
  `app/company_media/permissions.py:36-41`

  ```python
  if _matching_acl_allows(user, album, action):
      return True
  ```
  `app/company_media/permissions.py:64-68`

  ```python
  for flag in flags: setattr(entry, flag, bool(form.get(flag)))
  db.session.add(entry); db.session.commit(); return entry
  ```
  `app/company_media/services.py:91-95`
- Explanation: The secure PoC seeds the reporter with only a direct, active `can_share` ACL on one restricted album and no Company Media RBAC grants. The current POST returns 302 and rewrites that same ACL to add edit/delete/upload/download. This is a real privilege escalation but is bounded to the specific album, so HIGH is more accurate than CRITICAL.

## PoC execution

| ID | PoC file | Collection result | Test result today | Failure proves |
|---|---|---|---|---|
| 01 | `.audit/poc/critical_01_admin_self_grant_super_admin_test.py` | Collected | Expected failure | HTTP 302 and persisted `SUPER_ADMIN` role after an ADMIN self-edit. |
| 02 | `.audit/poc/critical_02_super_admin_password_reset_test.py` | Collected | Expected failure | Target super-admin hash changed and the temporary-password marker was rendered. |
| 03 | `.audit/poc/critical_03_roles_manage_self_grant_test.py` | Collected | Expected failure | HTTP 302 and a new `system.settings` grant on the actor's own role. |
| 04 | `.audit/poc/critical_04_project_membership_self_insert_test.py` | Collected | Expected failure | HTTP 302 and an active membership with every project capability. |
| 05 | `.audit/poc/critical_05_company_media_acl_escalation_test.py` | Collected | Expected failure | HTTP 302 and newly persisted edit/delete/upload/download ACL flags. |

Executed:

```text
PYTHONWARNINGS=error pytest -q -ra .audit/poc/*_test.py
```

Result: **5 collected; 5 expected failures; 0 unexpected errors; 0 collection errors.** The PoCs import the repository's existing `tests.conftest` app factory, database fixture, login flow, and its established CSRF-disabled test configuration; production CSRF remains initialized by the app factory.

## Totals

- Findings reviewed: **5**
- Confirmed: **5**
- False positive: **0**
- Uncertain: **0**
