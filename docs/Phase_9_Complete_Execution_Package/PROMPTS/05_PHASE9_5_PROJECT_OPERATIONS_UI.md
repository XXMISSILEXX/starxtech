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


# STEP 9.5 — UI Quản lý dự án & nhà thầu

## Mục tiêu

Xây màn hình vận hành chính Customer accordion → Project rows → Daily Report/Construction/Solution, cùng Project Workspace.

## UI requirements

### Main page

- Search Customer/Project.
- Accordion, one open by default.
- Customer header: name, project count, missing today count, contractor count.
- Project row: status, submitted today, construction/solution counts.
- Three equal-priority buttons:
  1. Báo cáo ngày
  2. Đối tác thi công
  3. Đối tác giải pháp
- Admin/custom-permission menu for edit/archive.
- Click Customer name → Customer Dashboard placeholder/route if not built yet; do not broken-link, use a safe interim detail route.
- Click Project name → Project Workspace.

### Workspace tabs

```text
Tổng quan
Báo cáo ngày
Báo cáo xuyên suốt
Vấn đề tồn đọng
Đối tác thi công
Đối tác giải pháp
```

Reuse existing reports/issues routes and components; do not duplicate controllers.

### Mobile

- badges wrap;
- report button full width if needed;
- contractor buttons next row;
- no horizontal overflow;
- accessible keyboard/aria accordion.

## Query requirements

- Effective project scope first.
- Batch contractor counts/submission state; no per-row queries.
- Only active/non-deleted records by default.
- Archived visible only with relevant permission/filter.

## Authorization

- main page `project_operations.view`;
- Customer/project/contractor actions each exact permission;
- UI visibility mirrors backend;
- unassigned projects not rendered or discoverable.

## Tests

- accordion/search JS or server behavior;
- scoped Customer grouping;
- no N+1 query threshold;
- counts by role;
- submitted/missing today Asia/Ho_Chi_Minh;
- custom read-only role;
- button/direct URL authorization;
- responsive markup/accessibility.

## Commands

```bash
pytest -q tests/test_rbac_navigation.py tests/test_mobile_nav_markup.py tests/test_report_create_entry.py tests/test_project_manager_permissions.py -vv
npm test
PYTHONWARNINGS=error pytest -q -ra
python -m compileall -q app tests migrations
pip check
flask security-audit
git diff --check
```

## Manual

- Desktop Chrome: accordion/search/actions.
- Mobile responsive mode.
- Verify no inaccessible project names in HTML/source.

## Commit

```bash
git add app/project_operations app/templates/project_operations app/static app/navigation.py tests docs/Phase9
git commit -m "feat(project-operations): add project and contractor management UI"
```
