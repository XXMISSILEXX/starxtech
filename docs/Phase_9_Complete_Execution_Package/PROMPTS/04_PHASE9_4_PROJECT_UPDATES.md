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


# STEP 9.4 — Báo cáo xuyên suốt và cập nhật theo contractor

## Mục tiêu

Tạo `ProjectUpdate` timeline riêng của mỗi project. Người có quyền có thể thêm cập nhật chung hoặc cập nhật cho đúng contractor assignment.

Ví dụ acceptance bắt buộc:

```text
An Bình Homeland
→ VTS / SOLUTION
→ HANDOVER
→ “Đã bàn giao xong 2 hạng mục”
```

Bản ghi phải xuất hiện ở project timeline và VTS timeline trong đúng project, không xuất hiện như update của VTS tại project khác.

## Model/migration

Theo `TARGET_DATA_MODEL.md`:

- project FK required;
- assignment FK nullable;
- update type;
- title/content/update_date;
- created/updated user;
- soft delete.

Validation:

- assignment belongs to same project;
- assignment not ended for new update;
- archived project/contractor policy;
- reasonable content limits;
- no attachments/workflow.

## Services/routes

- project update list with filters;
- contractor-assignment update list;
- create/edit/soft-delete;
- general update when assignment null;
- audit old/new values;
- latest update queries without N+1.

Suggested routes:

```text
GET  /projects/<id>/updates
GET  /projects/<id>/updates/new
POST /projects/<id>/updates
GET/POST /project-updates/<id>/edit
POST /project-updates/<id>/delete
GET  /project-assignments/<id>/updates
```

Use actual blueprint conventions.

## Authorization

- view/create/edit/edit_all/delete permission + project scope;
- creator may edit own only if chosen helper supports this;
- `edit_all` for managers;
- direct URL guessed IDs denied.

## UI

Timeline cards with:

- date;
- project;
- contractor and role if present;
- type badge;
- title/content;
- author/time;
- permission-aware actions.

Form launched from assignment locks contractor/project/role.

## Tests

- general update;
- assignment update same project;
- cross-project assignment rejected with no side effect;
- ended assignment rejected;
- soft delete hidden default but audit retained;
- own/edit_all rules;
- unassigned denial;
- latest/filter ordering;
- no DailyReport/PersistentIssue side effects.

## Commands

```bash
flask db migrate -m "add project update timeline"
flask db upgrade
flask db current

pytest -q tests/test_three_layer_authorization.py tests/test_project_manager_permissions.py -vv
PYTHONWARNINGS=error pytest -q -ra
python -m compileall -q app tests migrations
npm test
pip check
flask security-audit
git diff --check
```

## Commit

```bash
git add app/models app/project_operations app/templates/project_operations migrations/versions tests docs/Phase9
git commit -m "feat(project-updates): add continuous project update timeline"
```
