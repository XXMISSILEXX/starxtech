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


# STEP 9.7 — Dashboard query core và Project Dashboard

## Mục tiêu

Refactor/add dashboard core theo effective scope và xây Project Dashboard dựa trên năm section status hiện tại.

## Không làm

- Không health mapping.
- Không gọi ATTENTION/CRITICAL chung là ISSUE.
- Không link PersistentIssue với Daily Report.
- Không phá API chart cũ; giữ compatibility hoặc version endpoints.

## DashboardScope

Implement/test:

```text
scope_type
scope_id
permitted_project_ids
selected_date
from_date
to_date
```

Effective IDs = selected scope intersect authorization scope.

## Project dashboard components

Cards:

- project lifecycle status;
- submitted/missing today;
- active construction/solution counts;
- PersistentIssue count/by status separately;
- latest ProjectUpdate.

Charts:

1. Pie `DailyReportSection.status` for selected date.
2. Stacked 7/14/30-day section statuses:
   - INFO
   - GOOD
   - PROCESSING
   - ATTENTION
   - CRITICAL
3. Optional overall report status history as separate chart.
4. PersistentIssue status/severity separate.

Lists:

- missing today state;
- recent Daily Reports;
- ProjectUpdates;
- PersistentIssues;
- contractor assignments.

## Submission rules

- Expected population: ACTIVE project in scope.
- Missing report not in status charts.
- Coverage shown explicitly.

## Performance

- SQL aggregates/group by.
- No per-row loops.
- Add indexes only from query evidence.
- Test query count.

## APIs

JSON contracts stable and documented:

```text
labels
series/datasets
coverage
selected_date/range
empty_state
```

## Tests

- exact fixture calculations for all five statuses;
- no submitted report → empty chart, missing state;
- multiple reports/date range;
- old categories/statuses;
- custom-role assigned/unassigned/scope_all;
- API direct access;
- query-count threshold;
- current dashboard tests migrated by intent, not by weakening expectations.

## Commands

```bash
pytest -q tests/test_dashboard_issues.py tests/test_project_manager_permissions.py tests/test_three_layer_authorization.py -vv
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
git commit -m "feat(dashboard): add section-status project dashboard"
```
