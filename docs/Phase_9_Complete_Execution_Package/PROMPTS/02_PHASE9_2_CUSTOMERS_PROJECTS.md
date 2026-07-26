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


# STEP 9.2 — Customer foundation và Project grouping

## Mục tiêu

Tạo Customer domain riêng và nhóm Project hiện có theo Customer mà không phá reports/project scope.

## Source cần đọc

- `app/models/project.py`
- project admin routes/services/templates/tests
- migrations current head
- audit schema/data profile
- existing `ProjectStatus`

## Model/migration

1. Tạo `Customer` theo `TARGET_DATA_MODEL.md`.
2. Add nullable `projects.customer_id` FK/index.
3. Tái sử dụng Project status hiện tại; không tạo status cột mới.
4. Bổ sung lifecycle dates chỉ nếu chưa tồn tại và thật sự dùng trong UI.
5. Migration tạo Customer hệ thống `Khách hàng chưa phân loại` và backfill tất cả project null vào đó theo cách deterministic/idempotent.
6. Không set NOT NULL trong cùng migration nếu rehearsal chưa xác minh.
7. Không FK sang Partner Company.
8. Archive Customer; không hard-delete nếu có project.

## Service/routes UI tối thiểu

- List/search Customer.
- Create/edit/archive/restore nếu lifecycle hiện tại có restore convention.
- Assign/move Project to Customer.
- Validate normalized duplicate.
- Audit create/edit/archive/project move.
- Backend permission `customers.*` + effective project scope where applicable.

## Compatibility

- Existing `/projects`, reports, dashboard routes still work.
- Existing project IDs unchanged.
- Existing ProjectUser unchanged.
- “Chưa phân loại” group visible for accessible projects.

## Tests

- Migration upgrade on populated DB fixture.
- Existing project receives unclassified Customer.
- Customer unique/normalization.
- Archive does not delete Project/Report.
- Move project preserves reports/memberships/categories.
- Custom role view/manage matrix.
- Unassigned user cannot infer inaccessible projects via customer pages.
- Full Daily Report regression.

## Commands

```bash
flask db migrate -m "add customers and project grouping"
# inspect migration manually; remove accidental unrelated changes
flask db upgrade
flask db current

pytest -q tests/test_admin_screens.py tests/test_project_manager_permissions.py tests/test_report_create_entry.py -vv
PYTHONWARNINGS=error pytest -q -ra
python -m compileall -q app tests migrations
npm test
pip check
flask security-audit
git diff --check
```

## Commit

```bash
git add app/models app/<customer-or-project-operations-package> app/templates migrations/versions tests docs/Phase9
git commit -m "feat(projects): group projects by customer"
```
