# Phase 10 Closure and Phase 11 RC Readiness

## Release commit

`e03a865c8a060eff1fd3e75a593d815fd9ac0785` (`fix(security): tighten lifecycle and disclosure controls`). It is clean at the start of this closure review and is descended from `phase-9.0.0`.

## Remediation coverage summary

The canonical baseline is 34 CONFIRMED findings. All 34 are **FIXED AND VERIFIED** by current-source review plus the named regression tests below. `DELETE-PERM-001` is one canonical finding covering `REPORTS-004` and duplicate `ISSUE-002`; `ISSUE-002` is not counted again. `AI-002` remains a policy-invalid false positive and is excluded from this release gate.

| Classification | Count |
|---|---:|
| FIXED AND VERIFIED | 34 |
| FIXED BUT TEST EVIDENCE INCOMPLETE | 0 |
| NOT FIXED | 0 |
| REGRESSED | 0 |
| REQUIRES OPERATIONAL ACTION | 0 canonical findings |

## Finding-to-fix matrix

“Files” identifies the final behavioral implementation, not merely a commit-message match. `—` means the finding had no selected policy-valid PoC.

| Finding | Fix commit | Files | Regression test | PoC | Status |
|---|---|---|---|---|---|
| CRIT-01 | `459408e` | `app/admin/routes.py`, `services.py` | `test_admin_hierarchy.py::test_admin_cannot_assign_super_admin...` | `critical_01` pass | FIXED AND VERIFIED |
| CRIT-02 | `459408e` | `app/admin/routes.py`, `services.py` | `test_password_reset_respects_super_admin...` | `critical_02` pass | FIXED AND VERIFIED |
| CRIT-03 | `459408e` | `app/admin/routes.py`, `services.py` | `test_role_permission_management_enforces...` | `critical_03` pass | FIXED AND VERIFIED |
| CRIT-04 | `eaf1b99` | `app/admin/routes.py`, `app/project_memberships.py` | `test_assignment_permission_alone_cannot...` | `critical_04` pass | FIXED AND VERIFIED |
| CRIT-05 | `e5b13cf` | `app/company_media/{permissions,routes,services}.py` | `test_company_media_share_only_ceiling...` | `critical_05` pass | FIXED AND VERIFIED |
| CLI-001 | `137c79a` | `app/{config,security,__init__}.py`, entrypoint | `test_docker_deployment.py` startup cases | — | FIXED AND VERIFIED |
| ADMIN-001 | `459408e` | `app/admin/{routes,services}.py` | `test_activation_deactivation_respects...` | — | FIXED AND VERIFIED |
| ADMIN-002 | `e03a865` | `app/admin_storage/routes.py`, `app/csv_safety.py` | `test_csv_safe_cell_neutralizes...` | — | FIXED AND VERIFIED |
| REPORTS-001 | `1c417e6` | `app/projects/routes.py`, `app/reports/{create_v2,direct_uploads}.py` | `test_single_session_cancel_isolated...` | `reports_001` pass | FIXED AND VERIFIED |
| REPORTS-002 | `684f34a` | `app/reports/{routes,services}.py` | `test_report_list_and_today_use_report_scope...` | — | FIXED AND VERIFIED |
| REPORTS-003 | `684f34a` | `app/reports/{routes,services}.py` | `test_report_list_and_today_use_report_scope...` | — | FIXED AND VERIFIED |
| DELETE-PERM-001 | `1c417e6` | `app/attachments/routes.py`, `app/auth/permissions.py`, issue delete helper | `test_attachment_delete_requires...`; `test_issue_delete_requires...` | `issue_002` pass | FIXED AND VERIFIED |
| REPORTS-006 | `684f34a` | `app/reports/{routes,services}.py`, `app/projects/routes.py` | `test_archived_project_rejects_report...` | — | FIXED AND VERIFIED |
| UPLOAD-002 | `068c481` | `app/reports/direct_uploads.py`, `app/storage/providers.py` | `test_cancel_cleanup_failure_stays_cancelled...` | — | FIXED AND VERIFIED |
| PD-001 | `e5b13cf` | `app/project_documents/{permissions,services}.py` | `test_project_document_ceiling...` | — | FIXED AND VERIFIED |
| PD-003 | `e03a865` | `app/project_documents/{routes,services}.py` | `test_document_root_get_is_read_only...` | — | FIXED AND VERIFIED |
| CM-001 | `e5b13cf` | `app/company_media/{routes,services,permissions}.py` | `test_company_media_video_preview...` | — | FIXED AND VERIFIED |
| CM-002 | `e03a865` | `app/company_media/{routes,services}.py`, picker template/JS | `test_media_principal_picker_and_provider_error...` | — | FIXED AND VERIFIED |
| CM-005 | `e03a865` | `app/company_media/{routes,services}.py` | `test_media_principal_picker_and_provider_error...` | — | FIXED AND VERIFIED |
| PARTNER-001 | `e03a865` | `app/partners/lifecycle.py`, partner-company routes | `test_company_and_department_generic_edits...` | — | FIXED AND VERIFIED |
| PARTNER-002 | `e03a865` | `app/partners/lifecycle.py`, partner-company routes | `test_company_and_department_generic_edits...` | — | FIXED AND VERIFIED |
| PARTNER-003 | `068c481` | `app/{partner_photos,partners/routes,partner_companies/routes}.py` | `test_partner_photo_preview_is_authorised...` | — | FIXED AND VERIFIED |
| PARTNER-REL-001 | `e03a865` | `app/partner_relations/{routes,services}.py` | `test_relationship_graph_rejects_indirect_cycle...` | — | FIXED AND VERIFIED |
| PARTNER-REL-002 | `e03a865` | `app/partner_relations/{routes,services}.py` | `test_relationship_graph_rejects_indirect_cycle...` | — | FIXED AND VERIFIED |
| ATTACH-002 | `068c481` | `app/attachments/routes.py` | `test_attachment_authorisation_responses...` | — | FIXED AND VERIFIED |
| ISSUE-001 | `684f34a` | `app/issues/{routes,services}.py` | `test_global_issue_list_uses_issue_scope...` | — | FIXED AND VERIFIED |
| CUSTOMER-001 | `eaf1b99` | `app/customers/{routes,services}.py` | `test_customer_move_requires_project_and_both...` | `customer_001` pass | FIXED AND VERIFIED |
| CONTRACTOR-001 | `eaf1b99` | `app/project_operations/{routes,services}.py` | `test_assignment_rejects_cross_scope...` | `contractor_001` pass | FIXED AND VERIFIED |
| PROJECT-OPS-001 | `e03a865` | `app/project_operations/routes.py` | `test_foreign_project_update_assignment...` | — | FIXED AND VERIFIED |
| DASHBOARD-001 | `684f34a` | `app/dashboard/services.py`, project template | `test_project_dashboard_html_and_json_hide...` | — | FIXED AND VERIFIED |
| DASHBOARD-002 | `684f34a` | `app/dashboard/services.py`, project template | `test_project_dashboard_html_and_json_hide...` | — | FIXED AND VERIFIED |
| DASHBOARD-003 | `684f34a` | `app/dashboard/services.py`, project template | `test_project_dashboard_html_and_json_hide...` | — | FIXED AND VERIFIED |
| DASHBOARD-004 | `684f34a` | `app/dashboard/services.py`, scoped template | `test_contractor_dashboard_does_not_turn...` | — | FIXED AND VERIFIED |
| ACCOUNT-002 | `068c481` | `app/display_images.py`, account/admin/partner image routes | `test_display_image_replacement_and_delete...` | — | FIXED AND VERIFIED |

All eight remediation groups have reviewable commits: `459408e`, `eaf1b99`, `e5b13cf`, `1c417e6`, `684f34a`, `137c79a`, `068c481`, and `e03a865`.

## Final Python test results

Required command attempted from the project virtual environment:

```bash
source .venv/bin/activate && PYTHONWARNINGS=error python -m pytest -q -ra
```

`pytest --collect-only -q` reports **390 tests**. The execution harness terminated the full command at approximately 30 seconds after 38–39 progress markers and did not return a pytest summary or exit status; therefore the full-suite result is **INCOMPLETE, not a pass**. The project `.venv` is Python **3.10.12**, not the required 3.12.

Evidence completed under the same warning policy:

| Command scope | Result | Duration |
|---|---:|---:|
| Phase 10 remediation suites (`admin_hierarchy`, `phase10_project_scope`) | 15 passed | 12.38s |
| ACL/media and authorization-parity suites | 11 passed | 8.56s |
| Cleanup/delete suite | 13 passed | 9.98s |
| Lifecycle/disclosure and storage-lifecycle suites | 12 passed | 9.01s |
| Focused production/startup/Celery suites | 30 passed | 4.87s |

## Final security PoC results

Exact command (AI-002 intentionally excluded):

```bash
PYTHONWARNINGS=error pytest -q -ra \
  .audit/poc/critical_01_admin_self_grant_super_admin_test.py \
  .audit/poc/critical_02_super_admin_password_reset_test.py \
  .audit/poc/critical_03_roles_manage_self_grant_test.py \
  .audit/poc/critical_04_project_membership_self_insert_test.py \
  .audit/poc/critical_05_company_media_acl_escalation_test.py \
  .audit/poc/customer_001_project_move_authz_test.py \
  .audit/poc/contractor_001_cross_scope_assignment_test.py \
  .audit/poc/reports_001_cross_project_cleanup_test.py \
  .audit/poc/issue_002_delete_permission_test.py
```

Exit 0: **9 passed in 7.50s** (wall-clock 8s). All requested PoCs now assert the secure behavior. `AI-002` was read but not run as a release gate because it is not an unresolved vulnerability.

## JavaScript and compile results

`python -m compileall -q app tests`: exit 0, 0s. `npm test`: exit 0, **3 passed**, 0.440s (wall-clock 0s). Shell syntax validation (`sh -n docker-entrypoint.sh scripts/backup_db.sh scripts/backup_uploads.sh scripts/restore_db.sh scripts/start-media-worker.sh`): exit 0.

## Docker and Compose validation

- Safe-placeholder Compose validation: `APP_IMAGE=starx-report:e03a865 ... docker compose -f docker-compose.yml config --quiet`; exit 0.
- `docker build .`: exit 0; built local image `7333b8ea10bd`.
- `docker run --rm --entrypoint python 7333b8ea10bd --version`: exit 0, `Python 3.12.13`.
- Source and focused startup tests confirm an exact APP_ENV allow-list, failure on unknown/misspelled values, rejection of default secrets, SQLite/fake storage rejection in production, secret-file precedence, non-root Python-3.12 Gunicorn image, and no automatic production seed.
- `.dockerignore` contains `.git`, `.audit/`, `.env*`, `secrets/`, `backups/`, `deploy_backup_*/`, and `claude-partial-audit-backup/`.

No validation containers remain (`--rm` was used); no validation files were created.

## Worker and scheduler validation

Compose has the dedicated one-shot `migrate` service and starts `web`, `worker`, `scheduler` (Beat), and authenticated AOF Redis only after migration/Redis health. Worker queues are `media_image`, `media_video`, `storage_cleanup`, and `bulk_download`.

The import smoke passed for Flask/Celery/Gunicorn. The worker-entrypoint task registration check passed for `reports.cleanup_expired_upload_sessions`, `media.reconcile_media_jobs`, and `bulk_download.cleanup_expired`; all three are present in Beat. Required periodic schedules are therefore registered. Deployment docs match the stated architecture: host Nginx/PostgreSQL and systemd backup timer; Compose web/worker/Beat/Redis; external private S3.

## Predeployment repair dry-runs

Only the requested dry-runs were attempted:

```bash
flask provision-project-document-roots --dry-run
flask cleanup-unreferenced-display-images --dry-run
```

Both exited 1 before changing data because the configured PostgreSQL connection failed (`psycopg.OperationalError: connection is bad`). No `--apply` command was run. Consequently, whether staging data repair is required is **unknown** and must be determined by re-running both dry-runs against the Phase 11 staging PostgreSQL database before deployment.

## Repository integrity

- Initial and pre-report worktree status: clean; no uncommitted remediation code.
- No migration was introduced from `phase-9.0.0` to this release.
- No high-confidence private-key/token pattern was found in tracked content; `.env` files are not tracked (only safe examples are).
- No local database or generated artifact is tracked. However, the repository does track `deploy_backup_2026-07-14_142253/`, a deployment-backup directory. This fails the requested “no backup tracked” criterion even though `.dockerignore` excludes it from image context.
- `.audit/` was unchanged before this permitted closure file.

## Open uncertain findings

| Finding | Exact staging/runtime test | Expected secure result | Production blocker? | Owner and evidence required |
|---|---|---|---|---|
| UPLOAD-001 | Isolated staging S3/Celery worker processes a controlled malformed/format-confused image corpus using the deployed Pillow version. | Bytes are verified and unsafe inputs are rejected before harmful processing; workers remain healthy. | Yes if exploit/DoS is reproduced. | Application security + platform; corpus log, Pillow version/CVE assessment, worker resource metrics. |
| UPLOAD-003 | Two real PostgreSQL transactions synchronized at V2 presign with a session limit boundary. | One transaction serializes/rejects excess; no duplicate item or limit overrun persists. | Yes if a reproducible overrun occurs. | Application team; repeatable barrier test and committed-row/query evidence. |
| PD-002 | Product owner first decides whether archive revokes descendant access; then test direct descendant list/preview/download after ancestor archive. | If revocation is selected, all descendant access is denied. | Yes if revocation is policy and denial fails; policy decision is mandatory first. | Product owner + application team; written lifecycle decision and authenticated staging trace. |
| ATTACH-001 | Production-like S3/CDN preview/thumbnail load test with cache and quota/rate accounting enabled. | Equivalent egress/rate policy is enforced and accounting cannot be bypassed by bearer redirects. | Yes if unbounded/billable bypass is demonstrated. | Platform/S3 owner; CDN/S3 metrics, request traces, quota configuration. |
| ACCOUNT-001 | Deployed-Pillow controlled decompression-bomb/format-confusion corpus through synchronous display-image endpoints. | Input is rejected before excessive decode/resource use; request and service remain healthy. | Yes if practical DoS/CVE impact is reproduced. | Application security + platform; exact dependency version, corpus result, resource metrics. |

## Operational actions required on Cloudfly

1. Build and record an immutable image tag and resolved digest for this SHA; pin the reviewed base-image digest as the release action.
2. Configure protected secret files, external PostgreSQL, authenticated Redis, private S3, exact HTTPS CORS origin, trusted Nginx host, and no production seed variables.
3. Install/validate the documented Nginx reverse proxy and systemd backup timer; perform an isolated restore drill and preserve off-host encrypted backups.
4. In staging, run Compose config/up, migration, health, worker ping, Beat task schedule, direct upload/derivatives/bulk cleanup, and both dry-runs above.
5. Re-run the complete 390-test Python suite with `PYTHONWARNINGS=error` under Python 3.12 (CI or the built image) and retain its exit-0 summary.
6. Remove the tracked `deploy_backup_2026-07-14_142253/` directory from Git in an authorized follow-up change.

## Release verdict

**CONDITIONAL GO TO PHASE 11 STAGING.** This authorizes staging/infrastructure work only, never production. Conditions/blockers: the full 390-test Python gate lacks an exit-0 result under Python 3.12; both data-repair dry-runs require an available staging database; and the tracked deployment-backup directory must be removed in a separately authorized change. The five uncertain findings remain open for their specified staging/runtime evidence.
