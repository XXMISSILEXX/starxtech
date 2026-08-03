# Phase 12.4 — Mốc xanh trước triển khai

Ngày chạy: 2026-08-03

## Nghiệm thu Bước 0

| Nghiệm thu | Test/lệnh phủ |
| --- | --- |
| Toàn bộ kiểm thử Python xanh trước khi thay đổi Phase 12.4 | `pytest -p no:cacheprovider -q --durations=10` |
| Toàn bộ kiểm thử JavaScript xanh trước khi thay đổi Phase 12.4 | `npm test` |
| Số lượng khai báo test JavaScript được ghi nhận độc lập với output Node | `grep -h '^test(' tests_js/*.test.js \| wc -l` |
| Không có byte escape `\x` trong test tiến độ/dashboard | `grep -rnF '\x' tests/test_construction_progress_*.py tests/test_dashboard_*.py` |

Ba test bị skip là test PostgreSQL Phase 4/5 có điều kiện môi trường đã tồn tại từ
trước; không thuộc Phase 12.4.

## Output nguyên văn

```text
$ pytest -p no:cacheprovider -q --durations=10
.................................... [ 96%]
...................                                                      [100%]
============================= slowest 10 durations =============================
4.32s call     tests/test_security_hardening.py::test_reset_local_dev_runs_migrations_and_seeds_admin
3.10s setup    tests/test_three_layer_authorization.py::test_mixed_membership_capabilities_do_not_depend_on_global_role
2.61s setup    tests/test_reports_attachments.py::test_legacy_multipart_post_returns_405_without_side_effects
2.30s setup    tests/test_phase9_dashboard_ui_polish.py::test_reports_navigation_is_dashboard_first_on_desktop_and_mobile
1.99s setup    tests/test_partner_ux_improvements.py::test_relationship_delete_uses_post
1.75s setup    tests/test_partner_demo_seed.py::test_seed_partner_demo_creates_partner_values_with_partner_id
1.32s setup    tests/test_construction_progress_views.py::test_progress_tree_and_workspace_card_render_expected_content
1.21s setup    tests/test_construction_progress_group_batches.py::test_group_batch_allows_permitted_date_combinations[all_dates_empty----None-None-None-create]
1.08s setup    tests/test_construction_progress_entry_batches.py::test_entry_batch_hides_out_of_scope_item_and_rejects_future_date_without_writing
1.00s call     tests/test_dashboard_issues.py::test_system_project_activity_totals_and_percentages_are_additive_and_scoped
592 passed, 3 skipped in 380.17s (0:06:20)
```

```text
$ npm test

> test
> node --test tests_js/**/*.test.js

✔ tests_js/company-media-upload.test.js (55.147323ms)
✔ tests_js/construction-progress-overlays.test.js (399.060526ms)
✔ tests_js/daily-report-create-v2.test.js (431.333973ms)
✔ tests_js/media-cache-frontend.test.js (50.580567ms)
✔ tests_js/project-document-preview-download.test.js (440.400999ms)
✔ tests_js/report-direct-upload.test.js (358.807315ms)
✔ tests_js/scoped-dashboard-charts.test.js (395.309803ms)
✔ tests_js/theme-preferences.test.js (399.240494ms)
ℹ tests 8
ℹ suites 0
ℹ pass 8
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 452.644044

$ grep -h '^test(' tests_js/*.test.js | wc -l
33

$ node -v
v24.16.0

$ grep -rnF '\x' tests/test_construction_progress_*.py tests/test_dashboard_*.py
(rỗng)
```
