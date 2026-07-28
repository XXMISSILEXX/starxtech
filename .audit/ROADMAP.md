# Phase 10 Confirmed-Finding Roadmap

## Release position

**BLOCKED.** Confirmed Critical takeover paths, High cross-scope/destructive paths, and the confirmed fail-open deployment mode must be resolved before Phase 11. Operational deployment records are intentionally excluded here because they were not classified as security findings, but DEPLOY-001/002/003/006 must also be resolved by release operations.

## NOW — blocks Phase 11 deployment

| Order | Canonical ID | Source IDs | Severity | Fix objective | Effort | Must fix with | PoC |
|---:|---|---|---|---|---|---|---|
| 1 | CRIT-01 | 01 | Critical | Enforce target-role hierarchy and forbid self-promotion. | S | CRIT-02, CRIT-03 | critical_01 |
| 2 | CRIT-02 | 02 | Critical | Restrict password resets to higher/equal-safe authority; never expose reset secret to lower role. | S | CRIT-01 | critical_02 |
| 3 | CRIT-03 | 03 | Critical | Prevent self-role mutation and permission grants outside actor ceiling. | M | CRIT-01 | critical_03 |
| 4 | CRIT-04 | 04 | Critical | Require managed-project scope, target controls, and grant ceiling for memberships. | M | CUSTOMER-001, CONTRACTOR-001 | critical_04 |
| 5 | CLI-001 | CLI-001 | High | Fail closed on unknown/missing environment and default secret. | S | deployment startup tests | future |
| 6 | REPORTS-001 | REPORTS-001 | High | Cancel only the selected session; global cleanup only scheduled/admin scoped. | M | UPLOAD-002 | reports_001 |
| 7 | CUSTOMER-001 | CUSTOMER-001 | High | Require manage authority over both source and target customer. | S | contractor scope group | customer_001 |
| 8 | CONTRACTOR-001 | CONTRACTOR-001 | High | Require submitted contractor visibility and target-project management. | S | CRIT-04 | contractor_001 |
| 9 | PD-001 | PD-001 | High | Limit ACL grants to actor-authorised capability subset. | M | CRIT-05 | future ACL regression |
| 10 | CRIT-05 | 05 | High | ACL share authority must not alone create module/action authority or self-escalate. | M | PD-001 | critical_05 |
| 11 | CM-001 | CM-001 | High | Preview must never mint original video URL without download authority. | S | media download tests | future |

## NEXT — fix within two weeks after launch

| Canonical ID | Severity | Fix objective | Effort | Regression |
|---|---|---|---|---|
| ADMIN-001 | Medium | Add role hierarchy to deactivate/activate actions. | S | target-role test |
| REPORTS-002/003 | Medium | Scope report listing/today by `can_view_reports` and active projects. | M | custom-capability tests |
| DELETE-PERM-001 | Medium | Apply dedicated delete grants to both delete endpoints. | S | issue_002 + attachment test |
| REPORTS-006 | Medium | Reject report mutations for archived projects. | S | lifecycle test |
| ISSUE-001 | Medium | Query global issues by issue-view capability. | S | two-project scope test |
| DASHBOARD-001..004 | Medium | Apply resource-specific report/update/issue predicates in builders/API. | M | dashboard capability matrix |
| PARTNER-001/002 | Medium | Separate edit from restore/reactivation semantics. | S | lifecycle matrix |
| PROJECT-OPS-001 | Low | Return generic invalid-assignment error. | S | error-content test |
| UPLOAD-002 | Low | Track/cancel/reconcile uploaded V2 objects. | M | cancellation lifecycle test |
| ACCOUNT-002 | Low | Delete/lifecycle-account superseded objects. | M | quota/object test |
| CM-002/005 | Low | Minimise ACL directory and map provider errors to safe messages. | S | response tests |
| PARTNER-003 | Low | Use non-cacheable controlled preview response; avoid bearer redirect exposure. | M | headers test |
| PARTNER-REL-001/002 | Low | Validate graph globally; consistently hide archived companies. | M | graph/archive tests |
| ATTACH-002 | Low | Set `no-store` on authorisation redirects. | S | cache-header test |
| PD-003 | Low | Make root provisioning POST/creation-time, not GET. | S | CSRF/method test |
| ADMIN-002 | Low | Escape formula-leading CSV cells. | S | CSV fixture |

## LATER — tracked technical debt

No additional confirmed security findings are suitable for LATER. Reclassified deployment, test, concurrency, image-runtime, audit-log, and data-quality items remain in `VERIFIED.md` as non-security operational work.

## Fix dependency groups

| Group | Canonical IDs | Exact fix objective / expected files | Effort | Migration | Data repair | Rollback concern |
|---|---|---|---|---|---|---|
| Admin hierarchy | CRIT-01, CRIT-02, CRIT-03, ADMIN-001 | Central target-role/grant ceiling in `app/admin/routes.py` and services; tests for every role edge. | M | No | No | Avoid locking out sole SUPER_ADMIN. |
| Project/customer/contractor scope | CRIT-04, CUSTOMER-001, CONTRACTOR-001, PROJECT-OPS-001 | Central object-scope helpers in admin/customer/project-operation routes/services. | M | No | Review existing assignments/moves | Preserve legitimate global admins. |
| ACL permission ceiling | CRIT-05, PD-001, CM-001, CM-002 | Correct Company Media permissions/services and Documents grant writer; separate preview/download. | L | No | Review ACLs/URLs | Do not remove needed existing shares without migration plan. |
| Report lifecycle/destructive actions | REPORTS-001, REPORTS-002/003/006, DELETE-PERM-001, ISSUE-001 | Scope cleanup, listings, archive state, and delete helpers in reports/attachments/issues. | L | No | Inspect cancelled sessions/deletes | Do not globally delete pending storage on rollout. |
| Dashboard parity | DASHBOARD-001..004 | Put capability-aware filtering in dashboard services and both routes. | M | No | No | Charts may intentionally lose aggregate fields. |
| Storage/media lifecycle | UPLOAD-002, ACCOUNT-002, ATTACH-002, PARTNER-003 | Track object state, cache headers and controlled preview delivery. | M | No | Yes/UNCERTAIN for orphan inventory | Avoid deleting still-referenced objects. |
| Lifecycle/CSV integrity | PARTNER-001/002, PARTNER-REL-001/002, PD-003, ADMIN-002 | Explicit lifecycle transitions and escaped export. | M | No | Possibly hierarchy cleanup | Preserve archived history. |

Each group requires the listed regression tests in the same branch; all expected files are the route/service/permission modules named in its objective plus corresponding `tests/` files. No application patches are included here.

## Recommended fix order

1. Admin hierarchy: CRIT-01, CRIT-02, CRIT-03.
2. Arbitrary project control: CRIT-04, CUSTOMER-001, CONTRACTOR-001.
3. Scoped ACL/media escalation: CRIT-05, PD-001, CM-001.
4. Cross-session cleanup and destructive permission semantics: REPORTS-001, DELETE-PERM-001.
5. Report/issue/dashboard authorisation parity: REPORTS-002/003/006, ISSUE-001, DASHBOARD-001..004.
6. Bounded disclosure, lifecycle, and object-accounting fixes in NEXT order.
