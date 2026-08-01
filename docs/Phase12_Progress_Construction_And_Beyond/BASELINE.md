# Phase 12 baseline — Bước 0

Ngày chạy: 2026-08-01 (Asia/Ho_Chi_Minh)

## `pytest -p no:cacheprovider -q --durations=10 2>&1 | tail -40`

Output nguyên văn:

```text
..................................................s......ss............. [ 15%]
........................................................................ [ 30%]
........................................................................ [ 45%]
........................................................................ [ 60%]
........................................................................ [ 75%]
........................................................................ [ 90%]
............................................                             [100%]
============================= slowest 10 durations =============================
3.74s call     tests/test_security_hardening.py::test_reset_local_dev_runs_migrations_and_seeds_admin
2.32s setup    tests/test_security_hardening.py::test_response_security_headers_are_present
1.93s setup    tests/test_project_documents_upload.py::test_file_archive_restore_listing_and_preview
1.74s setup    tests/test_phase9_contractors.py::test_assignment_allows_both_roles_rejects_duplicate_and_allows_reassignment_after_end
1.47s setup    tests/test_phase10_acl_media_remediation.py::test_project_document_ceiling_covers_self_role_inheritance_and_atomic_rejections
1.35s setup    tests/test_partner_module.py::test_reporter_has_no_default_partner_access
1.20s setup    tests/test_media_processing_foundation.py::test_video_pipeline_uses_safe_argument_lists
1.06s setup    tests/test_dashboard_issues.py::test_system_dashboard_hub_exposes_permission_aware_canonical_dashboard_cards
0.88s setup    tests/test_company_media_upload_limits.py::test_company_media_presign_empty_and_per_file_structured_rejections
0.81s setup    tests/test_company_media_upload_limits.py::test_company_media_resolver_honours_each_override_and_rejects_invalid_values
473 passed, 3 skipped in 308.81s (0:05:08)
```

Tổng số test: 476 (473 pass, 3 skipped). Thời gian chạy thực tế: 308.81 giây
(5 phút 08 giây).

Ba test skip (môi trường không đặt biến kết nối PostgreSQL disposable):

1. `tests/test_company_media_phase4_postgresql.py::test_postgresql_concurrent_presign_and_complete_create_one_canonical_row` — `set PHASE4_POSTGRES_URL to run real PostgreSQL Phase 4 concurrency tests`.
2. `tests/test_company_media_phase5_postgresql.py::test_postgresql_two_cleanup_workers_serialize_and_do_not_double_delete` — `set PHASE5_POSTGRES_URL after upgrading the disposable PostgreSQL database`.
3. `tests/test_company_media_phase5_postgresql.py::test_postgresql_complete_cancel_race_preserves_consistent_terminal_state` — `set PHASE5_POSTGRES_URL after upgrading the disposable PostgreSQL database`.

## `npm test 2>&1 | tail -20`

Output nguyên văn:

```text

> test
> node --test tests_js/**/*.test.js

✔ tests_js/company-media-upload.test.js (47.324287ms)
✔ tests_js/daily-report-create-v2.test.js (420.698231ms)
✔ tests_js/media-cache-frontend.test.js (38.636672ms)
✔ tests_js/project-document-preview-download.test.js (397.107156ms)
✔ tests_js/report-direct-upload.test.js (334.788062ms)
✔ tests_js/scoped-dashboard-charts.test.js (370.003452ms)
✔ tests_js/theme-preferences.test.js (362.517461ms)
ℹ tests 7
ℹ suites 0
ℹ pass 7
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 429.756349
```
