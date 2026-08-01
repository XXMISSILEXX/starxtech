# Phase 12 — Kết quả triển khai tiến độ thi công

Ngày chốt: 2026-08-01
Revision migration: `6c53d69bfb07` (`phase12 construction progress`)

## 1. File thay đổi

| Nhóm file | Lý do |
| --- | --- |
| `app/models/progress.py`, `app/models/__init__.py`, `app/models/project.py`, `migrations/versions/6c53d69bfb07_phase12_construction_progress.py` | Bốn model tiến độ, export model, bốn capability của `ProjectUser`, và migration upgrade/downgrade. |
| `app/construction_progress/__init__.py`, `routes.py`, `services.py` | Blueprint, route HTML/JSON, kiểm quyền theo dự án, CRUD, tính toán, audit và POST/Redirect/GET. |
| `app/__init__.py`, `app/auth/permissions.py`, `app/navigation.py`, `app/permissions/registry.py`, `app/project_memberships.py` | Module gate, permission registry, helper/decorator capability, navigation, capability/preset. |
| `app/project_operations/routes.py` | Thẻ tiến độ và `summaries["progress"]` trong project workspace. |
| `app/templates/construction_progress/index.html`, `type_detail.html`, `item_detail.html` | Ba màn hình tiếng Việt, form CSRF, UI cấu trúc và phiếu, lịch sử, biểu đồ. |
| `app/static/js/construction-progress.js`, `tests_js/construction-progress.test.js` | Biểu đồ cột dọc; money dùng cột xếp lớp; kiểm tra JS. |
| `tests/test_construction_progress_models.py`, `services.py`, `authz.py`, `entries.py`, `views.py` | Test model, nghiệp vụ, ba lớp phân quyền, HTTP mutation/audit và rendering/escape. |
| `docs/Phase12_Progress_Construction_And_Beyond/BASELINE.md` | Baseline test trước triển khai. |
| `docs/Phase12_Progress_Construction_And_Beyond/PHASE12_RESULT.md` | Hồ sơ chốt phase này. |

## 2. Đối chiếu định nghĩa hoàn thành (đặc tả §12)

| Dòng | Trạng thái | Chứng cứ |
| --- | --- | --- |
| 1. Bốn bảng, migration, bốn capability, downgrade | Đạt | Migration `6c53d69bfb07`; kiểm thử SQLite upgrade/downgrade/upgrade ở mục 5. |
| 2. Ba lớp phân quyền | Đạt | Prefix gate, registry, capability/preset; `test_progress_route_matrix`. |
| 3. Thẻ mô đun đúng quyền, có số phụ | Đạt | `project_workspace()` và `test_progress_tree_and_workspace_card_render_expected_content`. |
| 4. Khai báo loại/khu vực/hạng mục và tạo phiếu qua UI | Đạt | Ba template có form CSRF gọi đủ route; HTTP mutation ở `test_progress_routes_enforce_read_structure_and_project_scope` và `test_entry_http_validation_and_idempotency`. |
| 5. Phần trăm ba cấp và biên | Đạt | `test_quantity_percentages_skip_unplanned_and_empty_groups`, `test_money_progress_uses_aggregated_values_and_decimal_precision`, `test_entry_http_create_update_delete_recalculates_and_audits`. |
| 6. Biểu đồ cột và số tổng khớp bảng | Đạt, không có browser E2E | JSON/service là nguồn số chung; `tests_js/construction-progress.test.js` kiểm cột dọc và stack money. |
| 7. Test §9 pass, không suppress warning | Đạt, với các lỗ hổng test ghi ở mục 3 | `pytest -rs`: 500 passed, 3 skipped; không warning mới. |
| 8. Audit mọi mutation phiếu và thay đổi cấu trúc | Đạt theo implementation; test trực tiếp chưa phủ hết cấu trúc | `services.py` gọi `log_audit` cho create/update/archive loại/khu vực/hạng mục và create/update/delete phiếu; test nội dung audit phiếu ở `test_entry_http_create_update_delete_recalculates_and_audits`. |
| 9. Không secret/dữ liệu thật | Đạt | Không thêm config/secret/data thật; kiểm tra diff Phase 12 chỉ gồm code, test, migration và tài liệu. |
| 10. Ghi lại `sync-permissions` sau deploy | Đạt | Mục 7 của tài liệu này. |

## 3. Đối chiếu kiểm thử bắt buộc (đặc tả §9)

| Yêu cầu | Test cụ thể / trạng thái |
| --- | --- |
| HTML/JSON: chưa đăng nhập, module gate, không phải thành viên, thiếu capability, có capability, VIEWER_ADMIN, ADMIN/SUPER_ADMIN | `test_progress_route_matrix`; `test_construction_progress_module_gate_rejects_user_without_reports_access`. Ma trận xác nhận các nhánh chặn không tạo hàng DB. |
| ID chéo dự án (`type_id`, `group_id`, `item_id`, `entry_id`) là 404 và không lộ tên | `test_progress_cross_project_ids_are_not_disclosed`. |
| Người tạo không được sửa/xóa phiếu người khác chỉ với capability tạo | `test_progress_entry_creator_cannot_edit_another_users_entry`. |
| Service trực tiếp: trùng ngày bị chặn, không tạo hàng thứ hai | `test_entries_validate_dates_duplicate_and_recalculate`; `test_progress_entry_is_unique_per_item_and_report_date`. |
| Form trùng ngày: thông báo tiếng Việt, một hàng | `test_entry_http_validation_and_idempotency`. |
| Ngày tương lai theo `local_today()` | `test_entry_http_validation_and_idempotency`. |
| Ngày quá khứ cho phép | `test_entries_validate_dates_duplicate_and_recalculate`. |
| `quantity <= 0` bị chặn | `test_entries_validate_dates_duplicate_and_recalculate`; `test_entry_http_validation_and_idempotency`. |
| Sửa phiếu tính lại, không cộng dồn | `test_entry_http_create_update_delete_recalculates_and_audits`; `test_entries_validate_dates_duplicate_and_recalculate`. |
| Xóa phiếu giảm lũy kế và audit có `old_values` | `test_entry_http_create_update_delete_recalculates_and_audits`; `test_entries_validate_dates_duplicate_and_recalculate`. |
| Gửi trùng request tạo phiếu chỉ một hàng | `test_entry_http_validation_and_idempotency`. |
| `planned_quantity = 0` loại khỏi trung bình, UI `—` | `test_quantity_percentages_skip_unplanned_and_empty_groups`; `test_progress_tree_and_workspace_card_render_expected_content`. |
| Khu vực rỗng loại khỏi trung bình loại | `test_quantity_percentages_skip_unplanned_and_empty_groups`. |
| `completed > planned` lưu giá trị thật, UI cap 100% | Giá trị thật 140% được phủ bởi `test_entry_http_create_update_delete_recalculates_and_audits`; **chưa có test UI riêng assert thanh/nhãn cap 100%**. |
| `value_mode = money` cộng dồn tiền | `test_money_progress_uses_aggregated_values_and_decimal_precision`. |
| Hàm phần trăm thuần với Decimal lẻ/làm tròn | `test_money_progress_uses_aggregated_values_and_decimal_precision`; **chưa có test riêng cho định dạng làm tròn tại HTML/chart**. |
| Constraint/model: unique tên, số không âm, value mode | `test_progress_names_are_unique_within_their_parent`, `test_progress_item_rejects_negative_planned_or_opening_quantity`, `test_progress_type_value_mode_only_accepts_quantity_or_money`. |
| UI ẩn mutation và escape input | `test_progress_templates_hide_structure_actions_and_escape_item_name`. |
| Chart cột dọc và money stack | `tests_js/construction-progress.test.js`; **chưa có test browser/integration assert tooltip và số tổng render**. |

Lưu ý: dòng có chữ **chưa có** là khoảng trống test được giữ nguyên để tránh biến báo cáo thành kết luận không có chứng cứ.

## 4. Chốt byte escape

Lệnh sau không in dòng nào (exit code 1 của `grep` nghĩa là không tìm thấy):

```text
$ grep -rn '\\x' tests/test_construction_progress_*.py
```

Không assertion Phase 12 nào dùng byte literal cho chuỗi tiếng Việt; assertion Unicode dùng `response.get_data(as_text=True)`.

## 5. Chạy thử migration trên SQLite tạm

DB dùng một lần: `/tmp/starx-phase12-b8-evidence.sqlite`. Đây không phải DB dev hay DB thật.

### Bước 1 — `flask db upgrade`

```text
$ DATABASE_URL=sqlite:////tmp/starx-phase12-b8-evidence.sqlite flask db upgrade
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 20260708_0001, initial schema
INFO  [alembic.runtime.migration] Running upgrade 20260708_0001 -> 20260708_0002, add project manager role
INFO  [alembic.runtime.migration] Running upgrade 20260708_0002 -> 20260708_0003, add partner management module
INFO  [alembic.runtime.migration] Running upgrade 20260708_0003 -> 20260709_0004, add partner field collections
INFO  [alembic.runtime.migration] Running upgrade 20260709_0004 -> 20260709_0005, improve partner relationship tree
INFO  [alembic.runtime.migration] Running upgrade 20260709_0005 -> 20260709_0006, add company departments
INFO  [alembic.runtime.migration] Running upgrade 20260709_0006 -> 20260709_0007, add special department flag
INFO  [alembic.runtime.migration] Running upgrade 20260709_0007 -> 20260710_0008, add partner department head flag
INFO  [alembic.runtime.migration] Running upgrade 20260710_0008 -> 20260719_0009, add canonical RBAC tables while preserving users.role
INFO  [alembic.runtime.migration] Running upgrade 20260719_0009 -> 20260720_0010, add storage batch foundation
INFO  [alembic.runtime.migration] Running upgrade 20260720_0010 -> 20260720_0011, add media processing foundation
INFO  [alembic.runtime.migration] Running upgrade 20260720_0011 -> 20260720_0012, add project documents core
INFO  [alembic.runtime.migration] Running upgrade 20260720_0012 -> 20260721_0013, add company media core
INFO  [alembic.runtime.migration] Running upgrade 20260721_0013 -> 20260722_0014, refactor authorization to global RBAC, project memberships, and ACL
INFO  [alembic.runtime.migration] Running upgrade 20260722_0014 -> 20260722_0015, allow project document custom roots
INFO  [alembic.runtime.migration] Running upgrade 20260722_0015 -> 20260722_0016, add module storage namespace and temporary bulk ZIP jobs
INFO  [alembic.runtime.migration] Running upgrade 20260722_0016 -> 20260722_0017, strict upload selections, quota events and legacy ZIP size
INFO  [alembic.runtime.migration] Running upgrade 20260722_0017 -> 20260722_0018, add ZIP stream download event fields
INFO  [alembic.runtime.migration] Running upgrade 20260722_0018 -> 20260723_0019, add storage dashboard aggregate indexes
INFO  [alembic.runtime.migration] Running upgrade 20260723_0019 -> 20260723_0020, add S3 references for partner photos and report attachments
INFO  [alembic.runtime.migration] Running upgrade 20260723_0020 -> 20260723_0021, enforce S3-only daily report attachments
INFO  [alembic.runtime.migration] Running upgrade 20260723_0021 -> 20260723_0022, add account display image and branding setting
INFO  [alembic.runtime.migration] Running upgrade 20260723_0022 -> 20260724_0023, remove Daily Reports soft-delete lifecycle
INFO  [alembic.runtime.migration] Running upgrade 20260724_0023 -> 20260724_0024, add direct upload lifecycle for daily reports
INFO  [alembic.runtime.migration] Running upgrade 20260724_0024 -> 20260724_0025, record finalized daily-report items and make media jobs idempotent
INFO  [alembic.runtime.migration] Running upgrade 20260724_0025 -> 20260725_0026, add daily report create idempotency key
INFO  [alembic.runtime.migration] Running upgrade 20260725_0026 -> aa468094da4f, add customers and project grouping
INFO  [alembic.runtime.migration] Running upgrade aa468094da4f -> b9f1c210e8d4, add project contractors and assignments
INFO  [alembic.runtime.migration] Running upgrade b9f1c210e8d4 -> c4d2e980f617, add project update timeline
INFO  [alembic.runtime.migration] Running upgrade 20260725_0026, c4d2e980f617 -> 20260729_0027, add persisted personal UI preferences
INFO  [alembic.runtime.migration] Running upgrade 20260729_0027 -> 20260730_0028, add Company Media selection-scoped idempotency
INFO  [alembic.runtime.migration] Running upgrade 20260730_0028 -> 20260731_0029, add Company Media upload cleanup timestamp
INFO  [alembic.runtime.migration] Running upgrade 20260731_0029 -> 6c53d69bfb07, phase12 construction progress
```

Kiểm bảng thực tế sau bước 1:

```text
tables= ['progress_entries', 'progress_groups', 'progress_items', 'progress_types']
```

### Bước 2 — tên constraint/index thực tế

```text
[('uq_progress_entries_item_date', True), ('ck_progress_entries_quantity_positive', True), ('uq_progress_types_project_name', True), ('uq_progress_groups_type_name', True), ('uq_progress_items_group_name', True)]
('ix_progress_entries_project_date', True)
```

### Bước 3 — server default bốn boolean

```text
[('can_create_progress_entries', 1, '0'), ('can_edit_all_progress_entries', 1, '0'), ('can_manage_progress_structure', 1, '0'), ('can_view_progress', 1, '0')]
```

`1` là `NOT NULL`; `0` là server default false trên SQLite, không phải `NULL`.

### Bước 4 — `flask db downgrade`

```text
$ DATABASE_URL=sqlite:////tmp/starx-phase12-b8-evidence.sqlite flask db downgrade 20260731_0029
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.runtime.migration] Running downgrade 6c53d69bfb07 -> 20260731_0029, phase12 construction progress
remaining_tables= []
remaining_project_users_booleans= []
```

### Bước 5 — upgrade lại

```text
$ DATABASE_URL=sqlite:////tmp/starx-phase12-b8-evidence.sqlite flask db upgrade
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260731_0029 -> 6c53d69bfb07, phase12 construction progress
$ DATABASE_URL=sqlite:////tmp/starx-phase12-b8-evidence.sqlite flask db current
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
6c53d69bfb07 (head)
```

Không chạy được PostgreSQL tạm qua Docker: `docker --version` và `docker compose version` có sẵn, nhưng `docker ps` trả `permission denied while trying to connect to the docker API at unix:///var/run/docker.sock`. Vì vậy chưa có kiểm chứng migration trên PostgreSQL.

## 6. Output test nguyên văn

### `pytest -rs`

```text
============================= test session starts ==============================
platform linux -- Python 3.10.12, pytest-8.3.2, pluggy-1.6.0
rootdir: /home/ubuntu/Documents/Construction_Management
configfile: pytest.ini
collected 503 items

tests/test_account_preferences.py .....                                  [  0%]
tests/test_admin_hierarchy.py ......                                     [  2%]
tests/test_admin_screens.py ........                                     [  3%]
tests/test_auth_permissions.py ...........                               [  5%]
tests/test_celery_context.py ...                                         [  6%]
tests/test_company_media_permissions_ux.py .........                     [  8%]
tests/test_company_media_phase4_idempotency.py ........                  [  9%]
tests/test_company_media_phase4_postgresql.py s                          [ 10%]
tests/test_company_media_phase5_cleanup.py ......                        [ 11%]
tests/test_company_media_phase5_postgresql.py ss                         [ 11%]
tests/test_company_media_upload_limits.py .......................        [ 16%]
tests/test_construction_progress_authz.py ...............                [ 19%]
tests/test_construction_progress_entries.py ..                           [ 19%]
tests/test_construction_progress_models.py .....                         [ 20%]
tests/test_construction_progress_services.py ...                         [ 21%]
tests/test_construction_progress_views.py ..                             [ 21%]
tests/test_daily_report_create_v2.py .............                       [ 24%]
tests/test_dashboard_issues.py ......................                    [ 28%]
tests/test_docker_deployment.py .......................                  [ 33%]
tests/test_document_library_custom_roots.py ..                           [ 33%]
tests/test_issue_buttons_html.py ......                                  [ 34%]
tests/test_login_membership_ux.py ....                                   [ 35%]
tests/test_media_cache.py .................                              [ 38%]
tests/test_media_processing_foundation.py ......                         [ 40%]
tests/test_mobile_nav_markup.py .                                        [ 40%]
tests/test_module_switch_visibility.py .....                             [ 41%]
tests/test_native_bulk_download_form.py ...                              [ 41%]
tests/test_partner_demo_seed.py ..................                       [ 45%]
tests/test_partner_module.py .......                                     [ 46%]
tests/test_partner_rbac.py ...                                           [ 47%]
tests/test_partner_ux_improvements.py ..............................     [ 53%]
tests/test_phase10_acl_media_remediation.py .....                        [ 54%]
tests/test_phase10_auth_parity.py ......                                 [ 55%]
tests/test_phase10_cleanup_delete.py .............                       [ 58%]
tests/test_phase10_lifecycle_disclosure.py ......                        [ 59%]
tests/test_phase10_project_scope.py .........                            [ 61%]
tests/test_phase10_storage_lifecycle.py ......                           [ 62%]
tests/test_phase9_contractors.py .......                                 [ 63%]
tests/test_phase9_customers.py .....                                     [ 64%]
tests/test_phase9_dashboard_ui_polish.py .....                           [ 65%]
tests/test_phase9_project_operations_ui.py ...                           [ 66%]
tests/test_phase9_project_updates.py .....                               [ 67%]
tests/test_phase9_rbac.py .........                                      [ 69%]
tests/test_phase9_today.py ..                                            [ 69%]
tests/test_phase9_vietnamese_ui.py ..                                    [ 69%]
tests/test_production_ops.py ....                                        [ 70%]
tests/test_project_customer_assignment.py .....                          [ 71%]
tests/test_project_documents_core.py .........                           [ 73%]
tests/test_project_documents_folder_lifecycle_ux.py ..                   [ 73%]
tests/test_project_documents_permissions_ux.py ....                      [ 74%]
tests/test_project_documents_upload.py ..................                [ 78%]
tests/test_project_documents_upload_ux.py ....                           [ 79%]
tests/test_project_manager_permissions.py .....                          [ 80%]
tests/test_rbac_navigation.py .                                          [ 80%]
tests/test_report_create_entry.py .....                                  [ 81%]
tests/test_reports_attachments.py ...............................        [ 87%]
tests/test_reports_route_namespace.py ...                                [ 88%]
tests/test_security_hardening.py ............                            [ 90%]
tests/test_signed_download_contract.py ........                          [ 92%]
tests/test_storage_dashboard.py ...                                      [ 92%]
tests/test_storage_foundation.py ...........................             [ 98%]
tests/test_storage_namespace_bulk_download.py .......                    [ 99%]
tests/test_three_layer_authorization.py ..                               [ 99%]
tests/test_vietnamese_dates.py .                                         [100%]

=========================== short test summary info ============================
SKIPPED [1] tests/test_company_media_phase4_postgresql.py:69: set PHASE4_POSTGRES_URL to run real PostgreSQL Phase 4 concurrency tests
SKIPPED [1] tests/test_company_media_phase5_postgresql.py:69: set PHASE5_POSTGRES_URL after upgrading the disposable PostgreSQL database
SKIPPED [1] tests/test_company_media_phase5_postgresql.py:93: set PHASE5_POSTGRES_URL after upgrading the disposable PostgreSQL database
================== 500 passed, 3 skipped in 335.87s (0:05:35) ==================
```

Ba test skip đều là test PostgreSQL Phase 4/5 đã có từ trước; không thuộc Phase 12. Lý do nguyên văn nằm ngay trong output trên.

### `npm test`

```text
> test
> node --test tests_js/**/*.test.js

✔ tests_js/company-media-upload.test.js (47.921437ms)
✔ tests_js/construction-progress.test.js (43.015089ms)
✔ tests_js/daily-report-create-v2.test.js (439.159369ms)
✔ tests_js/media-cache-frontend.test.js (42.566668ms)
✔ tests_js/project-document-preview-download.test.js (433.689785ms)
✔ tests_js/report-direct-upload.test.js (417.517205ms)
✔ tests_js/scoped-dashboard-charts.test.js (382.059243ms)
✔ tests_js/theme-preferences.test.js (359.675354ms)
ℹ tests 8
ℹ suites 0
ℹ pass 8
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 450.147525
```

## 7. Deploy

Trước khi bật module ở môi trường deploy, chạy:

```bash
flask db upgrade
flask sync-permissions --apply-defaults
```

Revision Phase 12 cần có: `6c53d69bfb07`.

## 8. Quyết định, lệch đặc tả và giới hạn

- Phân quyền dùng wrapper mới trên `_project_permission_required`; không dùng `project_write_required`, vì primitive đó hardcode `can_edit_all_reports`.
- Chọn cùng cây dữ liệu/service làm nguồn cho HTML và chart JSON; money tính tổng planned/completed thay vì trung bình phần trăm.
- Route mutation dùng `<action>` có allowlist `if/elif/else abort(404)`, thay vì hai path riêng `/edit` và `/delete` như §7.3. Đây là lệch cú pháp route nhưng không làm nới quyền.
- Nhánh thành công của POST ban đầu trả JSON `201/204`, di sản stub Bước 4. Commit `aec442f` đã đổi toàn bộ mutation sang POST/Redirect/GET, có flash tiếng Việt; `chart-data` vẫn là JSON.
- SQLite migration test không chứng minh kiểu `Numeric(18,3)`, thực thi `CheckConstraint`, unique constraint hay `SELECT FOR UPDATE` dưới tải đồng thời giống PostgreSQL. PostgreSQL tạm chưa chạy được vì không có quyền Docker daemon.
- Không có import/export Excel, upload ảnh phiếu, biểu đồ đường lũy kế, approval workflow hoặc dashboard toàn hệ thống; đây là ngoài phạm vi §10.
- Những khoảng trống test UI/browser và audit cấu trúc được nêu ở mục 3, không bị che bằng assertion trạng thái HTTP.
