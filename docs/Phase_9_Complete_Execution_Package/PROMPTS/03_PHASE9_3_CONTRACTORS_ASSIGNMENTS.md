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


# STEP 9.3 — ProjectContractor và Assignment foundation

## Mục tiêu

Tạo catalog nhà thầu/đối tác dự án và quan hệ nhiều-nhiều theo role, hoàn toàn độc lập Partner module.

## Model

Tạo:

- `ProjectContractor`
- `ProjectContractorAssignment`
- enums/constants role/status theo convention repo

Rules:

- Role `CONSTRUCTION` hoặc `SOLUTION`.
- Status `ACTIVE/PAUSED/COMPLETED/ENDED`.
- Cùng contractor/project được phép hai role.
- Chặn duplicate non-ended assignment cùng project+contractor+role.
- End assignment set `ended_on`; không delete.
- Contractor archive chỉ khi không có active assignment hoặc service xử lý rõ.
- Historical assignments vẫn query được.

## Services

- create/edit/archive contractor;
- assign contractor to project;
- update assignment status/note/dates;
- end assignment;
- count active assignments by project/role;
- accessible query intersect project scope;
- audit all mutations.

## Routes/UI tối thiểu

Chỉ CRUD/service UI functional, chưa cần accordion final:

```text
/project-operations/contractors
/project-operations/contractors/<id>
/projects/<id>/contractors/construction
/projects/<id>/contractors/solution
```

Exact prefix phải phù hợp current blueprints và avoid collision.

## Authorization

- catalog actions use `project_contractors.*`;
- assignment actions use `contractor_assignments.*` plus project scope;
- global catalog viewer không tự có project data ngoài scope;
- UI buttons match backend.

## Tests

- no FK/import to Partner models;
- contractor participates multiple projects/customers;
- both roles same project permitted;
- duplicate active same role rejected;
- ended then new assignment policy tested;
- archive/end preserve history;
- custom role matrix and unassigned denial;
- CSRF/method tests;
- audit records.

## Commands

```bash
flask db migrate -m "add project contractors and assignments"
flask db upgrade
flask db current

pytest -q tests/test_project_manager_permissions.py tests/test_three_layer_authorization.py tests/test_admin_screens.py -vv
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
git commit -m "feat(contractors): add project contractor assignments"
```
