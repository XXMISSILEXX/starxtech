Bạn đang làm việc trong repository:

```text
~/Documents/Construction_Management
```

Đây là một step của Phase 9: biến phân hệ Báo cáo hàng ngày thành Quản lý dự án & nhà thầu.

Trước khi sửa code:

1. Đọc `AGENTS.md` hoặc hướng dẫn repo nếu có.
2. Đọc:
   - `docs/Phase_9_Complete_Execution_Package/MASTER_CONTEXT.md`
   - `docs/Phase_9_Complete_Execution_Package/FINAL_DECISIONS.md`
   - tài liệu TARGET liên quan;
   - `docs/Phase_9_Complete_Execution_Package/REFERENCE/Pre_Phase9_Audit/`.
3. Ghi branch, HEAD, working tree, migration current/head.
4. Đọc đầy đủ source liên quan, không chỉ grep snippets.
5. Không reset/stash/overwrite pre-existing changes.

Ràng buộc bất biến:

- Không dùng Company/Partner/PartnerRelationship cho Customer/contractor Phase 9.
- Không thêm health status hoặc đổi Daily Report status.
- Không tự tạo/link PersistentIssue từ Daily Report.
- Không tạo OpenIssue hoặc observation table.
- Không tạo ProjectReportItem.
- Không rewrite Daily Report V2, direct S3, HEIC, finalize, attachment hay Celery.
- Không hard-code chức năng mới theo tên custom role; dùng permission codes.
- Không skip/xfail/broad mock để che lỗi.
- Không commit khi gate chưa đạt.
- Không thực hiện công việc ngoài scope của step.


# STEP 9.6 — Hôm nay, Reports navigation, Configuration hub và category safety

## Mục tiêu

Hoàn thiện bốn navigation của Reports module, Today workflow và tích hợp cấu hình hiện có. Chỉ cải tiến Daily Report additive, không đổi status/transport.

## Navigation

```text
Hôm nay
Quản lý dự án & nhà thầu
Dashboard quản trị
Cấu hình
```

- permission-based visibility;
- active module Reports;
- no broken links;
- direct URL backend guards.

## Today

- selected date mặc định theo `Asia/Ho_Chi_Minh`;
- project `ACTIVE` trong effective scope;
- grouped by Customer;
- report exists → detail;
- missing → create if `can_create_report`, otherwise read-only missing state;
- user no projects → 200 empty state, not 403;
- paused/completed/archived not expected in Today.

## Configuration hub

Link theo permission tới existing:

- Project management;
- memberships;
- ReportCategory per project;
- roles/permissions;
- Customer/contractor admin.

Không viết lại admin screens.

## Category safety

Audit source again. Implement only these additive improvements:

1. `DailyReportSection` category name/icon snapshots, nullable, if approved by source compatibility.
2. New finalize writes snapshots.
3. Detail/edit fallback for old rows.
4. Enforce active required categories only after create form prepopulates them and V2 validation/finalize agree.
5. Do not alter section status.
6. Do not link issue.

If required-category enforcement would break legitimate optional section behavior, document and split into a separately reviewed commit; do not force it silently.

## Project status gate

- new reports only for `ACTIVE` projects;
- existing reports remain viewable/editable according to current policy;
- V2 preflight and finalize both revalidate status;
- duplicate date remains before upload.

## Tests

- navigation custom-role matrix;
- Today empty/submitted/missing;
- timezone date boundary;
- project status preflight creates zero session/object/report;
- category snapshot history;
- required categories if implemented;
- all V2 direct-upload/idempotency/HEIC tests unchanged.

## Commands

```bash
pytest -q tests/test_rbac_navigation.py tests/test_mobile_nav_markup.py tests/test_report_create_entry.py tests/test_daily_report_create_v2.py tests/test_reports_attachments.py -vv
npm run build:heic-preview
npm test
PYTHONWARNINGS=error pytest -q -ra
python -m compileall -q app tests migrations
pip check
flask security-audit
git diff --check
```

If snapshot migration added:

```bash
flask db migrate -m "snapshot report category presentation"
flask db upgrade
flask db current
```

## Manual mandatory

- JPG/PNG/HEIC preview before Save.
- No application upload before Save.
- Duplicate date no upload.
- Original preserved.
- Today routing.

## Commit

```bash
git add app/navigation.py app/project_operations app/reports app/models app/templates app/static migrations/versions tests docs/Phase9
git commit -m "feat(reports): add today navigation and configuration integration"
```
