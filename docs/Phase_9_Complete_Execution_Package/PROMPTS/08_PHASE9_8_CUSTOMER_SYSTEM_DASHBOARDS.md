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


# STEP 9.8 — Customer và System Dashboards

## Mục tiêu

Tái sử dụng DashboardScope/core để aggregate Customer và toàn system mà không rò rỉ project.

## Customer Dashboard

- Child projects within Customer AND effective authorization.
- Cards: active projects, submission rate, missing, distinct contractors, PersistentIssue count.
- Pie/stacked section status five values.
- Submission by project.
- Overall report status by project optional.
- PersistentIssue by project/status/severity.
- ProjectUpdate timeline.

## System Dashboard

- Same core across all effective projects.
- Cards: Customer/project/contractor/report submission/PersistentIssue.
- Tabs:
  - Tổng quan
  - Báo cáo
  - Vấn đề tồn đọng
  - Nhà thầu
- Avoid more than 5–6 charts per visible tab.

## Scope/security

- `dashboards.customer.view`/`dashboards.system.view` or exact approved registry codes.
- System normally requires `projects.scope_all`; a user without it must not silently see system aggregates.
- Customer page for partial-scope user shows only accessible child projects and clearly labels partial scope if business chooses. Prefer deny Customer dashboard without all-customer scope unless semantics are documented.
- No ID enumeration leakage.

## Data rules

- distinct contractor by active assignments;
- missing reports denominator explicit;
- archived/paused/completed excluded from expected today population;
- PersistentIssue separate from reports;
- ProjectUpdate separate.

## Tests

- two Customers, multiple projects, partial assignments;
- exact distinct counts;
- missing denominator;
- five-status aggregate;
- custom global read-only role;
- partial scope policy;
- direct URL 403;
- query performance.

## Commands

```bash
pytest -q tests/test_dashboard_issues.py tests/test_three_layer_authorization.py tests/test_rbac_navigation.py -vv
npm test
PYTHONWARNINGS=error pytest -q -ra
python -m compileall -q app tests migrations
pip check
flask security-audit
git diff --check
```

## Commit

```bash
git add app/dashboard app/templates/dashboard app/static tests docs/Phase9 migrations/versions
git commit -m "feat(dashboard): add customer and system scopes"
```
