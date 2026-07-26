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


# STEP 9.9 — Contractor Dashboard

## Mục tiêu

Xây dashboard nhẹ cho ProjectContractor, tập trung participation, assignment và ProjectUpdate gắn assignment.

## Components

Cards:

- active project count;
- Customer count;
- construction role count;
- solution role count;
- assignment status counts;
- latest update.

Charts/lists:

- project by Customer;
- assignment by role/status;
- ProjectUpdate timeline by project/type;
- project list with current overall Daily Report status as context only.

PersistentIssue:

- nếu hiển thị, đặt dưới “Bối cảnh dự án”;
- không gọi là trách nhiệm contractor;
- không filter/assign issue to contractor vì schema không có relation.

Daily Report:

- không dùng section status pie/stacked để đánh giá contractor;
- không tạo contractor score.

## Scope

- Contractor dashboard results include only assignments whose projects user can access, unless `projects.scope_all`.
- Catalog existence must not reveal inaccessible project names.
- Ended assignment history visible with filter and permission.

## Tests

- contractor across multiple Customers/projects;
- same contractor two roles;
- partial project scope;
- timeline only matching assignment;
- general project update not mislabeled contractor update;
- ended assignment historical display;
- no section-status contractor analytics;
- custom contractor-viewer role.

## Commands

```bash
pytest -q tests/test_three_layer_authorization.py tests/test_rbac_navigation.py tests/test_dashboard_issues.py -vv
npm test
PYTHONWARNINGS=error pytest -q -ra
python -m compileall -q app tests migrations
pip check
flask security-audit
git diff --check
```

## Manual

Verify VTS update “Đã bàn giao xong 2 hạng mục” appears:

1. VTS assignment timeline in An Bình Homeland.
2. Project ongoing timeline.
3. Project dashboard recent updates.
4. Customer dashboard recent updates.
5. VTS dashboard.

It must not appear as VTS update in another project.

## Commit

```bash
git add app/dashboard app/project_operations app/templates app/static tests docs/Phase9
git commit -m "feat(dashboard): add contractor scope"
```
