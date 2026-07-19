# Security risk review

## Top findings

1. **High — coarse partner write scope.** `PROJECT_MANAGER` can create/edit partners, companies, departments and relationships globally; these records have no project/owner scope. This conflicts with the stated future default (PM view only unless ticked). Protect partner module first with explicit permissions.
2. **High — confusing admin semantics.** `super_admin_required()` permits `ADMIN`; `_require_super_admin_post()` also permits ADMIN, while templates hide forms for non-SUPER_ADMIN. Route naming/UI can lead to incorrect assumptions. Split explicit permissions and add tests.
3. **High — no protection for last SUPER_ADMIN.** User deactivate/edit/reset routes have no invariant preventing loss of final active super-admin; no role-management guard exists yet.
4. **Medium — role checks dispersed.** Authorization is split across helper, route, service and Jinja hard-codes. A new route can easily omit a backend check; menu visibility is not a security boundary.
5. **Medium — project edit is broad.** Reporter can edit any report in an assigned project, not only their own. It may be correct, but the business rule is not encoded distinctly; `ProjectUser.role_in_project` is unused.

## Additional findings

- Report attachment access is comparatively sound: private endpoint, project permission and path traversal containment. It lacks download audit and abstraction for non-local storage.
- Partner company/departments UI shows write controls without a matching `can_edit` guard in one template; backend blocks it, but fix UI once RBAC exists.
- Partner mutations generally lack audit records; reports/issues/admin have partial audit coverage. Permission, file, partner/company/relationship and download actions need audit coverage.
- Dashboard API protection relies on global login and service scoping rather than explicit module permission; move to `reports.dashboard.view`.
- All partner read data is global for roles currently allowed; sensitive contacts/relationships require future scope decision.
- POST routes use global CSRF; preserve it. Authorization must be checked before mutation in every POST, including presigned-upload initiation.

## Priority actions

1. Add registry/tables/CLI and test deny-by-default without changing current behavior until mappings are seeded.
2. Replace partner access/write checks with permissions and remove global PM write by default.
3. Add last-SUPER_ADMIN invariant, audit role changes and distinct dangerous permissions.
4. Apply report/issue/attachment permission+scope helpers; explicitly decide reporter own vs assigned-project edit.
5. Build documents/photos only on private storage and the above policies; add S3 after local implementation works.
