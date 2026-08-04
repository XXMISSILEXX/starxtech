# Phase 12.3 — Mốc xanh trước triển khai

Ngày chạy: 2026-08-03

## Nghiệm thu Bước 0

| Nghiệm thu | Test/lệnh phủ |
| --- | --- |
| Toàn bộ kiểm thử Python xanh trước khi thay đổi Phase 12.3 | `pytest -p no:cacheprovider -q --durations=10` |
| Toàn bộ kiểm thử JavaScript xanh trước khi thay đổi Phase 12.3 | `npm test` |
| Số lượng khai báo test JavaScript được ghi nhận độc lập với output Node | `grep -h '^test(' tests_js/*.test.js \| wc -l` |

Ba test bị skip là test PostgreSQL Phase 4/5 có điều kiện môi trường đã tồn tại từ
trước; không thuộc Phase 12.3.

## Output nguyên văn

```text
$ pytest -p no:cacheprovider -q --durations=10
..................................................s......ss............. [ 12%]
........................................................................ [ 25%]
........................................................................ [ 38%]
........................................................................ [ 51%]
........................................................................ [ 64%]
........................................................................ [ 77%]
........................................................................ [ 90%]
....................................................                     [100%]
============================= slowest 10 durations =============================
4.18s call     tests/test_security_hardening.py::test_reset_local_dev_runs_migrations_and_seeds_admin
2.67s setup    tests/test_security_hardening.py::test_csp_allows_only_valid_configured_s3_endpoint_origin
2.33s setup    tests/test_project_documents_core.py::test_assigned_scope_and_restricted_acl_remain_for_project_roles
1.56s setup    tests/test_mobile_nav_markup.py::test_mobile_account_actions_are_in_offcanvas_and_topbar_is_mobile_hidden
1.51s call     tests/test_phase10_lifecycle_disclosure.py::test_foreign_project_update_assignment_returns_generic_error
1.35s setup    tests/test_dashboard_issues.py::test_system_dashboard_payload_query_count_is_not_linear
1.26s call     tests/test_partner_ux_improvements.py::test_partner_form_uses_department_select_not_free_text
1.06s setup    tests/test_construction_progress_entry_list.py::test_entry_tab_uses_sql_page_filters_and_distinguishes_empty_states
0.88s setup    tests/test_company_media_upload_limits.py::test_company_media_presign_batch_file_boundaries[49-None]
0.85s call     tests/test_construction_progress_views.py::test_progress_templates_hide_structure_actions_and_escape_item_name
553 passed, 3 skipped in 357.08s (0:05:57)
```

```text
$ npm test

> test
> node --test tests_js/**/*.test.js

✔ tests_js/company-media-upload.test.js (58.040939ms)
✔ tests_js/construction-progress-overlays.test.js (417.558407ms)
✔ tests_js/daily-report-create-v2.test.js (410.126633ms)
✔ tests_js/media-cache-frontend.test.js (46.637522ms)
✔ tests_js/project-document-preview-download.test.js (447.349645ms)
✔ tests_js/report-direct-upload.test.js (380.167729ms)
✔ tests_js/scoped-dashboard-charts.test.js (426.22005ms)
✔ tests_js/theme-preferences.test.js (356.411514ms)
ℹ tests 8
ℹ suites 0
ℹ pass 8
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 463.151399

$ grep -h '^test(' tests_js/*.test.js | wc -l
33

$ node -v
v24.16.0
```
