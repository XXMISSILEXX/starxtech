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
ℹ tests 32
ℹ suites 0
ℹ pass 32
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

## 9. Phụ lục — xác minh trên PostgreSQL thật (bổ sung sau Bước 8)

Mục 8 ghi "PostgreSQL tạm chưa chạy được vì không có quyền Docker daemon". Giới
hạn đó đã được khắc phục và các kiểm tra dưới đây **đã chạy thật**. Mục 8 giữ
nguyên làm hồ sơ thời điểm; mục này là kết quả bổ sung.

Môi trường: PostgreSQL **16.14** trong container dùng-một-lần
`127.0.0.1:55433`, database và role `starx_phase4`. Không có database nào của
môi trường dev bị chạm tới; container đã bị xoá sau khi xong.

### 9.1 Toàn bộ chuỗi migration áp dụng được từ đầu

`flask db upgrade` chạy trọn lịch sử migration trên database rỗng và kết thúc
đúng ở revision Phase 12 `6c53d69bfb07`. Không phải chỉ migration Phase 12 —
toàn bộ chuỗi từ đầu dự án đều áp dụng được trên PostgreSQL.

### 9.2 Những thứ SQLite không chứng minh được

Constraint Phase 12 tồn tại trên PostgreSQL với đúng tên đã đặc tả:

```
uq_progress_entries_item_date                  u
ck_progress_entries_quantity_positive          c
uq_progress_groups_type_name                   u
uq_progress_items_group_name                   u
uq_progress_types_project_name                 u
ck_progress_types_value_mode                   c
ck_progress_items_planned_quantity_nonnegative c
ck_progress_items_opening_quantity_nonnegative c
```

Kiểu số đúng `numeric(18,3)` cho cả bốn cột khối lượng:
`progress_entries.quantity`, `progress_items.planned_quantity`,
`progress_items.opening_quantity`, `progress_items.completed_quantity`.

Bốn cột capability trên `project_users` đều `column_default = false` và
`is_nullable = NO`.

### 9.3 Vòng lặp downgrade/upgrade

`flask db downgrade` từ `6c53d69bfb07` về `20260731_0029` xoá sạch:

```
bảng progress_*  còn lại: 0
cột %progress% trên project_users còn lại: 0
```

`flask db upgrade` sau đó áp dụng lại thành công. Không có lỗi thứ tự drop FK.

### 9.4 Ba test PostgreSQL trước đây bị skip — nay đã chạy

Ba test này bị skip trong mọi lần chạy của Phase 11 và Phase 12 vì thiếu
`PHASE4_POSTGRES_URL` / `PHASE5_POSTGRES_URL`, và hồ sơ Phase 4/5 ghi là "not
executed". Nay đã chạy trên PostgreSQL 16.14 thật:

```
tests/test_company_media_phase4_postgresql.py                    1 passed in 0.49s
  test_postgresql_concurrent_presign_and_complete_create_one_canonical_row  PASSED

tests/test_company_media_phase5_postgresql.py                    2 passed in 0.66s
  test_postgresql_two_cleanup_workers_serialize_and_do_not_double_delete    PASSED
  test_postgresql_complete_cancel_race_preserves_consistent_terminal_state  PASSED
```

### 9.5 Giới hạn còn lại

Mô đun tiến độ thi công **vẫn chưa có** test đồng thời trên PostgreSQL riêng của
nó. Hai điều sau đây vẫn chưa được chứng minh dưới tranh chấp thật:

1. `uq_progress_entries_item_date` chặn hai phiếu cùng (hạng mục, ngày) khi hai
   request đến đồng thời — hiện chỉ chứng minh được app tự kiểm tuần tự.
2. `recalculate_item_completed()` với `SELECT ... FOR UPDATE` không bị lost
   update khi hai người tạo phiếu cho cùng hạng mục ở hai ngày khác nhau.

Khuôn để viết: `tests/test_company_media_phase4_postgresql.py` (fixture
`pg_app`, gate bằng biến môi trường, `ThreadPoolExecutor(max_workers=2)`).
Lệnh dựng lại môi trường:

```bash
docker run -d --name starx-phase4-pg -e POSTGRES_USER=starx_phase4 -e POSTGRES_PASSWORD=starx_phase4 -e POSTGRES_DB=starx_phase4 -p 127.0.0.1:55433:5432 postgres:16
```

## 10. Phase 12.1 — UX, xoá cứng và batch (2026-08-02)

Các commit Phase 12.1:

| Bước | Commit | Kết quả |
| --- | --- | --- |
| 0 | `5d4d909` | Ghi baseline 12.1. |
| 1 | `5042dbc` | `decimal_places`, định dạng `vn_number`, validation độ chính xác. |
| 2 | `dcbf77e` | Xoá cứng ba cấp, audit snapshot, bỏ archive/filter `is_active`. |
| 3 | `02f69a7` | Migration xoá `is_active` sau khi dữ liệu ẩn development được chủ dự án dọn qua UI. |
| 4 | `a36c95f` | Overlay batch tạo/sửa khu vực và hạng mục. |
| 5 | `6983719` | Overlay batch phiếu cập nhật ngày. |
| 6 | `6372e06` | Bỏ canvas/chart JavaScript khỏi trang chi tiết; giữ route `chart-data` cho dashboard sau này. |
| 7 | `bbb4694` | Bảng dữ liệu thuần, gập/mở khu vực, nhãn chưa kế hoạch/vượt kế hoạch. |

### Chức năng đã chốt

- Hiển thị số theo `decimal_places` (0–3), `None` thành `—`, phần trăm luôn một chữ số thập phân.
- Không thể hạ độ chính xác nếu kế hoạch, mang sang hoặc phiếu hiện hữu sẽ bị làm tròn; quy tắc áp dụng cho cả sửa lẻ và batch.
- Xoá loại/khu vực/hạng mục là xoá cứng theo thứ tự phiếu → hạng mục → khu vực → loại, có xác nhận và audit đủ dữ liệu phiếu trước khi xoá.
- Tạo/sửa khu vực và tạo phiếu ngày đều là transaction tất-cả-hoặc-không; overlay giữ nguyên dữ liệu đã nhập khi server từ chối.
- Route `chart-data` vẫn tồn tại và vẫn có test phân quyền, nhưng không còn được render ở trang chi tiết.
- Bổ sung sau khi chủ dự án test tay: số hiển thị kiểu Việt trước đây không đọc lại được khi nhập. `services.py` nay dùng một parser chung, không phụ thuộc locale, cho mọi đường ghi hạng mục/phiếu; parser hiểu dấu chấm hoặc dấu phẩy đối xứng, từ chối trường hợp mơ hồ ở độ chính xác 3, và giữ nguyên validation số âm, dương và `decimal_places`.

### Kiểm thử chốt Phase 12.1

```text
$ pytest -p no:cacheprovider -q
549 passed, 3 skipped in 344.35s (0:05:44)
```

Skip là ba test PostgreSQL Phase 4/5 đã có từ trước khi không cấu hình URL PostgreSQL.

### Việc phải làm khi deploy

1. Xác nhận backup tự động đã bật và đã restore thử độc lập; audit log phải có màn hình quản trị trước khi cho người dùng thật dùng xoá cứng.
2. Khi nâng từ bản có `is_active`, cho chủ dự án tự xoá hết bản ghi đang ẩn trên UI trước khi chạy migration drop cột; không dùng SQL/script để xoá dữ liệu thật.
3. Chạy `flask db upgrade`, sau đó chạy lệnh đồng bộ permission đã ghi ở mục 7 của tài liệu này.
4. Smoke test: mở trang chi tiết loại, tạo batch khu vực, tạo batch phiếu, thử một lỗi validation và xác nhận dữ liệu overlay còn nguyên.
5. Nếu khối lượng trở thành số liệu nghiệm thu/thanh toán hoặc bị ràng buộc lưu trữ, xem lại quyết định xoá cứng theo mục 12 của tài liệu Phase 12.1.

## 11. Phase 12.2 — lỗi overlay, danh sách phiếu và tab (2026-08-03)

### Commit

- `57b6435` — baseline Phase 12.2.
- `d65371c` — căn hàng overlay, placeholder và nhãn “Đã làm trước đó”.
- `c718c79` — lỗi batch có cấu trúc và gắn cạnh đúng ô.
- `39b2f3c` — mở lại overlay tin cậy, bỏ flash cảnh báo cấp trang.
- `d3f8fc1` — trang hạng mục chỉ còn số liệu và lịch sử; bỏ `create_entry`.
- `8f91df8` — tab URL thật, danh sách phiếu có filter/phân trang, sửa/xóa từ danh sách.

### Đối chiếu đặc tả

| Mục | Trạng thái | Bằng chứng |
| --- | --- | --- |
| 1. Lỗi trong overlay | Đạt | `test_create_group_batch_rejects_duplicate_names_in_payload_and_keeps_form_values`, `test_overlay_reopening_waits_for_domcontentloaded_when_the_page_is_still_loading` |
| 2. Danh sách phiếu | Đạt | `test_entry_tab_uses_sql_page_filters_and_distinguishes_empty_states`, `test_entry_list_edit_failure_and_delete_keep_list_state_and_audit`, `test_entry_list_edit_rejects_future_date_and_excess_precision_without_writing` |
| 3. Lệch dòng và nhãn | Đạt | `test_progress_templates_use_placeholders_and_no_longer_call_opening_quantity_mang_sang` |
| 4. Trang hạng mục | Đạt | `test_item_detail_shows_history_without_create_form_and_removed_create_route_is_404` |
| 5. Hai tab | Đạt | `test_entry_tab_uses_sql_page_filters_and_distinguishes_empty_states`, `test_progress_route_matrix` |

Đã bỏ route `create_entry`, giảm từ 18 xuống 17 route. Flash cảnh báo cấp trang khi batch lỗi cũng đã bỏ; câu tổng kết lỗi nằm trong overlay.

Gantt được **hoãn có chủ ý**: `ProgressItem` không có cột ngày. Hai hướng đã cân nhắc: thêm `planned_start_date`/`planned_end_date` để vẽ kế hoạch và thực tế; hoặc chỉ suy thanh thực tế từ phiếu đầu đến phiếu gần nhất, nhưng không có mốc kế hoạch.

Bài học: test JSDOM đánh giá script trên DOM hoàn chỉnh nên không bắt lỗi thứ tự tải. Guard thực sự là assertion tầng server so vị trí `data-open-progress-modal` trước script trong HTML.

Nợ kỹ thuật đã biết: `vn_number` raise `ValueError` khi `places` ngoài 0–3 (hiện CheckConstraint ngăn được); chưa có test chống hồi quy riêng cho việc không còn input trong bảng dữ liệu và không còn canvas biểu đồ.

Deploy: chạy `flask db upgrade` tới revision mới nhất. Phase 12.2 không thêm permission, **không cần** `sync-permissions`.

⚠️ **Cảnh báo cho người deploy — đừng đọc câu trên rời khỏi ngữ cảnh.** Câu đó chỉ đúng cho
riêng vòng 12.2. **Phase 12 đã thêm 6 permission code** (`construction_progress.*`, xem mục 7).
Nếu server đang ở trạng thái trước Phase 12 thì lần deploy này vẫn phải chạy đủ hai lệnh:

```bash
flask db upgrade && flask sync-permissions --apply-defaults
```

Bỏ lệnh thứ hai thì thẻ "Quản lý tiến độ thi công" sẽ **không hiện với bất kỳ ai ngoài
Quản trị tổng**, vì thẻ được lọc bằng RBAC toàn cục chứ không phải capability dự án
(`project_workspace()` dùng `current_user.can(...)`). Triệu chứng khi đó trông như mô đun bị
lỗi, dù code hoàn toàn đúng.

Giới hạn: suite dùng SQLite in-memory, không chứng minh tranh chấp PostgreSQL; mô đun tiến độ chưa có test đồng thời riêng và đang có task riêng.

## 12. Phase 12.3 — Biểu đồ Gantt theo khu vực (2026-08-03)

### Commit

- `cad69e4` — ghi mốc xanh `BASELINE_12_3.md` trước khi thay đổi.
- `fd522f4` — thêm ba cột ngày, hai `CheckConstraint` và migration Gantt.
- `138335c` — thêm ba ô ngày trong overlay batch, bố cục hai dòng con và validation dùng chung ở service.
- `baa1c43` — suy diễn khoảng Gantt thuần cho hạng mục, khu vực và các hạng mục bị loại.
- `fcb8a23` — render tab `?tab=gantt` bằng HTML/CSS server-side, trục, thanh và các nhãn.
- `d7a8688` — sửa ba đặc tả Phase 12 dùng đúng guard `grep -rnF '\x'`.
- `16c74f3` — sửa tương phản tab, nhãn vạch hôm nay và danh sách hạng mục bị loại sau cổng dừng 2.

### Đối chiếu đặc tả Gantt

| Mục | Trạng thái | Bằng chứng kiểm thử |
| --- | --- | --- |
| 1. Thay đổi dữ liệu | Đạt | `test_progress_item_database_rejects_unpaired_planned_dates`, `test_progress_item_database_rejects_reversed_planned_dates`, `test_progress_item_database_allows_valid_planned_dates`, `test_progress_item_database_allows_all_gantt_dates_empty` |
| 2. Quy tắc suy diễn | Đạt | `test_item_gantt_timeline_uses_earliest_actual_evidence`, `test_item_gantt_timeline_marks_manual_actual_start_without_entries_as_point`, `test_item_gantt_timeline_has_no_actual_bar_without_start_or_entries`, `test_group_gantt_timeline_uses_only_scheduled_items_and_excludes_empty_group`, `test_gantt_timeline_for_type_counts_excluded_items_and_omits_empty_groups` |
| 3. Nhập ngày trong overlay | Đạt | `test_progress_item_overlay_uses_two_subrows_for_nine_fields`, `test_group_batch_date_validation_reopens_overlay_and_rolls_back_every_row`, `test_group_batch_allows_permitted_date_combinations` |
| 4. Vẽ biểu đồ | Đạt | `test_gantt_axis_selects_daily_weekly_and_monthly_ticks_at_thresholds`, `test_gantt_chart_axis_expands_to_today_without_extending_actual_bar_to_today`, `test_gantt_tab_renders_server_side_bars_and_required_disclosures`, `test_gantt_tab_empty_state_and_invalid_tab_follow_the_tab_contract`, `test_progress_route_matrix` |

Không có mục nào trong §1–§4 không áp dụng.

### Dữ liệu và deploy

`progress_items` có thêm ba cột `nullable=True`: `planned_start_date`,
`planned_end_date`, `actual_start_date`. Migration revision là `233012a8c8dc`; nó thêm
hai constraint `ck_progress_items_planned_dates_paired` và
`ck_progress_items_planned_date_order`, đồng thời `downgrade()` bỏ đúng ba cột và hai
constraint.

Phase 12.3 **KHÔNG thêm permission** nên không cần `sync-permissions`, nhưng deploy vẫn
cần chạy:

```bash
flask db upgrade
```

### Quyết định thiết kế Gantt

Có `actual_start_date` nhập tay nhưng **KHÔNG** có `actual_end_date`. Ngày kết thúc thực
tế suy từ ngày phiếu muộn nhất và tự cập nhật mỗi lần có phiếu mới; nhập tay sẽ lỗi thời
và tạo hai nguồn cho cùng một sự thật.

Nguyên tắc phân định ở §0 của đặc tả:

> **Ngày bắt đầu thực tế nhập tay** vì nó thỏa hai điều kiện. Hệ thống **không thể biết**
> nó — với hạng mục đã thi công trước khi dùng hệ thống, `opening_quantity` cho biết khối
> lượng nhưng không có mốc thời gian nào. Và nó **ghi một lần là xong** — ngày một công
> việc bắt đầu không thay đổi về sau, nên trường này không bao giờ lỗi thời.
>
> **Ngày kết thúc thực tế suy từ phiếu** vì cả hai điều kiện đều không thỏa. Hệ thống đã
> biết nó: chính là ngày phiếu muộn nhất. Và nếu nhập tay thì nó **sẽ lỗi thời** — người
> dùng điền một lần lúc khai kế hoạch rồi không ai quay lại sửa khi công việc thực sự
> xong. Một ngày kết thúc cũ trên Gantt tệ hơn không có ngày nào, vì nó khẳng định một
> điều sai. Phiếu thì được nhập hằng ngày như một phần công việc, nên ngày suy từ phiếu
> luôn đúng mà không ai phải nhớ gì.
>
> Ngoài ra, nhập tay ngày kết thúc sẽ tạo hai nguồn cho cùng một sự thật và chúng sẽ lệch
> nhau — trái nguyên tắc mô đun đã chốt từ Phase 12: chỉ hạng mục nhỏ mang dữ liệu gốc,
> mọi thứ suy ra được thì không lưu.

Thanh thực tế không kéo tới hôm nay. Khi phiếu cuối đã cũ, thanh dừng ở ngày phiếu đó;
khoảng trống tới vạch hôm nay là thông tin rằng công việc đang dừng. Kéo thanh tới hôm
nay sẽ che mất thông tin này. Trường hợp “Điện” ở cổng dừng 2 kết thúc đúng tại vạch hôm
nay là đúng dữ liệu: phiếu cuối rơi đúng vào hôm nay, không phải lỗi render.

### Bổ sung sau cổng dừng 2

Chủ dự án tìm ra ba lỗi giao diện và commit `16c74f3` đã sửa:

1. Tab đang chọn dùng `nav-pills` có chữ xanh trên nền xanh ở theme dự án; đổi sang
   `nav-tabs` đồng bộ với tab loại và giữ tương phản ở cả light/dark theme.
2. Danh sách hạng mục bị loại chỉ có tên hạng mục; đổi thành `Khu vực — Hạng mục` để
   phân biệt tên trùng ở hai khu vực.
3. Nhãn “Hôm nay” che nhãn mốc trục; bỏ chữ, giữ vạch đỏ với `title` và `aria-label`.

Lỗi tương phản tab đã tồn tại từ Phase 12.2 nhưng test không bắt được vì chuỗi nhãn vẫn
có trong HTML — chỉ màu chữ sai. Bài học: assertion HTML chỉ khẳng định chuỗi tồn tại
không chứng minh người dùng đọc được nó; với trạng thái active phải khẳng định class/kiểu
tạo tương phản, và cần kiểm thử hiển thị ở light/dark theme.

Bài học thứ hai: guard `grep -rn '\x'` dùng trong ba vòng là sai. Trong BRE, `\x` khớp
mọi dòng có chữ `x`, không phải literal byte escape. Dạng đúng là:

```bash
grep -rnF '\x' tests/test_construction_progress_*.py
```

Ba đặc tả Phase 12.1, 12.2 và 12.3 đã được sửa bằng `d7a8688`; mọi phase sau dùng dạng
có `-F`.

### Nợ kỹ thuật và giới hạn đã biết

- `vn_number` vẫn raise `ValueError` khi `places` ngoài 0–3.
- Chưa có test chống hồi quy riêng cho việc không còn ô input trong bảng dữ liệu.
- Mô đun tiến độ chưa có test đồng thời riêng trên PostgreSQL.
- Suite chạy SQLite in-memory nên không chứng minh hành vi PostgreSQL đồng thời.

## 13. Phase 12.4 — Dashboard tiến độ thi công (2026-08-03)

### Commit

| Commit | Kết quả |
| --- | --- |
| `4bde515` | Trau nhóm nút và thẻ overlay tiến độ đã hoàn tất trước vòng dashboard; bổ sung hồ sơ theo yêu cầu. |
| `c936ab7` | Ghi mốc xanh `BASELINE_12_4.md`. |
| `b0e72b2` | Thêm hàm thuần `type_progress_summary()` và test quy tắc suy diễn. |
| `284512f` | Hiện khối tiến độ capability-scoped trên dashboard dự án. |
| `a2ee57f` | Thêm hub “Dashboard tiến độ thi công”, permission và phân trang SQL. |
| `39759f5` | Thêm bộ chọn cặp dự án–giai đoạn và biểu đồ cột khu vực. |
| `ae4a293` | Resolve CSS token trước khi đưa màu vào Chart.js, sửa cột đen ở light/dark theme. |

### Đối chiếu đặc tả §1–§4

| Mục | Trạng thái | Bằng chứng kiểm thử |
| --- | --- | --- |
| 1. `type_progress_summary()` | Đạt | `test_type_progress_summary_leaves_dates_and_days_none_without_scheduled_groups`, `test_type_progress_summary_counts_single_planned_day_inclusively`, `test_type_progress_summary_marks_done_before_overdue_when_complete`, `test_type_progress_summary_counts_only_scheduled_incomplete_items_as_overdue` |
| 2. Khối tiến độ trên dashboard dự án | Đạt | `test_project_dashboard_renders_capability_scoped_progress_block_without_project_percent`, `test_project_dashboard_hides_progress_block_without_progress_capability`, `test_project_dashboard_shows_progress_instruction_without_progress_types` |
| 3. Hub Dashboard tiến độ thi công | Đạt | `test_progress_dashboard_route_matrix`, `test_progress_dashboard_scopes_rows_to_progress_capability_without_global_scope`, `test_progress_dashboard_navigation_card_respects_permission`, `test_progress_dashboard_orders_statuses_and_uses_sql_pagination`, `test_progress_dashboard_query_count_is_not_linear` |
| 4. Kế hoạch thi hành và cổng dừng | Đạt | Baseline `c936ab7`; chủ dự án đã nghiệm thu khối dự án và card hub trên dữ liệu thật. |

### Bổ sung §5 — bộ chọn và biểu đồ khu vực

- Bộ chọn là cặp dự án–giai đoạn, dùng form `GET` với `?type_id=` và tự submit. Mặc định là giai đoạn đầu tiên theo thứ tự bảng đã sắp xếp; `type_id` ngoài phạm vi quay về lựa chọn mặc định mà không lộ tên dự án/giai đoạn.
- Dropdown chỉ chứa dự án người xem tiếp cận được đồng thời có `can_view_progress`. Không thêm permission hay capability.
- Canvas chỉ render khi giai đoạn có khu vực. Div bọc có chiều cao xác định, `position: relative`, và Chart.js có `maintainAspectRatio: false`; không còn layout cao vô hạn.
- Chế độ khối lượng dùng một màu để so sánh độ lớn. Chế độ tiền dùng hai phần xếp lớp “Đã hoàn thành”/“Còn lại”, có nhãn và viền cho phần còn lại, không dựa riêng vào màu.
- Chart.js không hiểu chuỗi CSS `var(...)` khi vẽ canvas. Bản sửa `ae4a293` dùng `getComputedStyle(document.documentElement).getPropertyValue(token).trim()` cho `--sx-primary`, `--sx-chart-good`, `--sx-chart-neutral`; token có giá trị ở cả light/dark theme và test chặn `backgroundColor` bắt đầu bằng `var(`.

Bằng chứng: `test_progress_dashboard_chart_selector_scopes_pairs_and_defaults_to_first_problem`, `test_progress_dashboard_chart_out_of_scope_type_falls_back_without_disclosure`, `test_progress_dashboard_chart_empty_states`, `loads chart data and renders one vertical bar for every area`, `does not create a Chart when chart-data has no area labels`, `uses completed and remaining stacked datasets for money progress`.

Chủ dự án đã nghiệm thu bằng mắt bộ chọn và biểu đồ ở cả theme sáng/tối sau bản sửa màu.

### Dữ liệu, permission và deploy

Phase 12.4 không đổi schema và không có migration; **không cần** `flask db upgrade` riêng cho vòng này. Permission mới duy nhất là `dashboards.progress.view`, được default cho `ADMIN` và `VIEWER_ADMIN`.

Deploy cần chạy:

```bash
flask sync-permissions --apply-defaults
```

Database development đã được đồng bộ sau Bước 3 với kết quả `roles=0 permissions=1 grants=2 deprecated-orphan=0`.

Không có phần trăm tổng dự án hay toàn hệ thống. Phần trăm chỉ thuộc dòng giai đoạn, vì chưa chốt quy tắc trọng số giữa các giai đoạn.

### Kiểm thử chốt

```text
pytest -p no:cacheprovider -q --durations=10
620 passed, 3 skipped in 392.63s (0:06:32)

npm test
9 passed, 0 failed
```

`grep -h '^test(' tests_js/*.test.js | wc -l` là `36`; `node -v` là `v24.16.0`; `grep -rnF '\x' tests/test_construction_progress_*.py tests/test_dashboard_*.py` không có output.

### Giới hạn còn lại

- Suite vẫn dùng SQLite in-memory; không chứng minh hành vi PostgreSQL đồng thời.
- Mô đun tiến độ chưa có test tranh chấp PostgreSQL riêng cho phiếu trùng ngày hoặc `recalculate_item_completed()`.
- Test HTML/JS bảo vệ hợp đồng và màu đã resolve, nhưng không tự chứng minh được chất lượng thẩm mỹ; cổng nghiệm thu thực vẫn là kiểm tra bằng mắt ở cả hai theme.
