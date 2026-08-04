# Phase 13 — Mốc xanh trước triển khai

Ngày chạy: 2026-08-04 (Asia/Ho_Chi_Minh)  
Commit hiện tại: `63a811e docs(phase13): spec audit log policy and admin viewer`

## Nghiệm thu Bước 0

| Nghiệm thu | Test/lệnh phủ |
| --- | --- |
| Toàn bộ kiểm thử Python xanh trước khi thay đổi Phase 13 | `pytest -p no:cacheprovider -q --durations=10` |
| Toàn bộ kiểm thử JavaScript xanh trước khi thay đổi Phase 13 | `npm test` |
| Số lượng khai báo test JavaScript được ghi nhận độc lập với output Node | `grep -h '^test(' tests_js/*.test.js \| wc -l` |

## Output nguyên văn

```text
$ pytest -p no:cacheprovider -q --durations=10
.......................................................s......ss........ [ 11%]
........................................................................ [ 22%]
........................................................................ [ 34%]
........................................................................ [ 45%]
........................................................................ [ 56%]
........................................................................ [ 68%]
........................................................................ [ 79%]
........................................................................ [ 91%]
........................................................                 [100%]
============================= slowest 10 durations =============================
4.31s call     tests/test_security_hardening.py::test_reset_local_dev_runs_migrations_and_seeds_admin
3.02s setup    tests/test_security_hardening.py::test_seed_admin_updates_requested_account_and_never_echoes_password
2.56s setup    tests/test_project_documents_core.py::test_move_rejects_root_cross_project_archived_parent_and_duplicate
2.20s setup    tests/test_phase10_cleanup_delete.py::test_cancel_never_removes_finalized_report_attachment
2.00s setup    tests/test_partner_demo_seed.py::test_seed_partner_demo_sets_normal_department_heads_on_partners
1.45s setup    tests/test_dashboard_issues.py::test_project_dashboard_hides_progress_block_without_progress_capability
1.31s setup    tests/test_construction_progress_services.py::test_quantity_percentages_skip_unplanned_and_empty_groups
1.28s call     tests/test_dashboard_progress.py::test_progress_dashboard_chart_out_of_scope_type_falls_back_without_disclosure
1.08s setup    tests/test_construction_progress_deletions.py::test_progress_structure_has_no_archive_state_or_actions
1.00s setup    tests/test_construction_progress_authz.py::test_construction_progress_module_gate_rejects_user_without_reports_access
629 passed, 3 skipped in 397.55s (0:06:37)
```

```text
$ npm test

> test
> node --test tests_js/**/*.test.js

✔ tests_js/company-media-upload.test.js (55.147603ms)
✔ tests_js/construction-progress-overlays.test.js (455.031043ms)
✔ tests_js/daily-report-create-v2.test.js (469.048825ms)
✔ tests_js/media-cache-frontend.test.js (47.306694ms)
✔ tests_js/progress-dashboard-chart.test.js (393.104125ms)
✔ tests_js/project-document-preview-download.test.js (505.540678ms)
✔ tests_js/report-direct-upload.test.js (366.468048ms)
✔ tests_js/scoped-dashboard-charts.test.js (420.450818ms)
✔ tests_js/theme-preferences.test.js (416.025225ms)
ℹ tests 9
ℹ suites 0
ℹ pass 9
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 523.426315

$ grep -h '^test(' tests_js/*.test.js | wc -l
36
```
