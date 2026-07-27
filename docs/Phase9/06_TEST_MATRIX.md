# Test matrix

| Area | Required coverage |
| --- | --- |
| Migration/model | Upgrade populated DB, nullable/backfill/constraint validation, lifecycle and uniqueness. |
| RBAC/scope | SUPER/ADMIN/VIEWER/legacy/custom roles × assigned/unassigned projects; direct URL and navigation visibility. |
| Customer/contractor/update | CRUD/archive/end/soft-delete, same-project assignment validation, no cross-scope leak, audit. |
| Today/dashboard | active project denominator, missing list, 5 direct section statuses, system/customer/project/contractor scope and query count. |
| System analytics doughnuts | 7/30/90 periods, additive activity totals/percentages, effective scope, empty states, deterministic project colours, Vietnamese tooltip/summary and no empty Chart instance. |
| Configuration navigation | Direct project/customer/contractor/category/membership URLs retain Reports shell with active Cấu hình; System Admin has no project item and `/admin/roles` remains System Admin. |
| Regression | Daily Report V2, entry, attachment, security, private URL and idempotent-finalize tests. |
| Manual when UI changes | Chrome + iPhone Safari direct upload, HEIC preview, retry, bookmarks and mobile navigation. |

No skip, xfail, broad mock, or old-test expectation rewrite is permitted to obtain a green gate.
