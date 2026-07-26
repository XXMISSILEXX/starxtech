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


# STEP 9.1 — RBAC và custom-role foundation

## Mục tiêu

Bổ sung permission catalogue để custom roles có thể truy cập độc lập Today, project operations, dashboards, Customer, contractor, assignment và ProjectUpdate. Không tạo domain tables ở step này.

## Đọc source

- `app/models/rbac.py`, `app/models/user.py`
- `app/permissions/`
- `app/auth/permissions.py`
- `app/project_memberships.py`
- `app/navigation.py`
- role permission admin routes/templates/tests
- DB permission/role rows read-only

## Thiết kế

1. Reuse exact existing permissions nếu có.
2. Thêm only missing codes từ `TARGET_RBAC_AND_CUSTOM_ROLES.md`.
3. Thêm `projects.scope_all` để custom role có global project scope, nhưng không thay SUPER_ADMIN bypass.
4. Cập nhật project-scope helpers theo hướng:
   - admin/SUPER compatibility;
   - `projects.scope_all` cho custom/global scope;
   - còn lại dùng ProjectUser/capabilities hiện tại.
5. Navigation helpers có thể nhận permission mới nhưng chưa show route chưa tồn tại; feature links phải tránh broken link.
6. `sync-permissions --apply-defaults` không được xóa custom DB roles/grants.
7. Permission UI nhóm rõ:
   - Điều hướng Reports;
   - Khách hàng;
   - Nhà thầu dự án;
   - Assignment;
   - Báo cáo xuyên suốt;
   - Dashboard.
8. Audit role permission changes.

## Tests bắt buộc

- Registry sync idempotent.
- Unknown permission deny.
- Custom role with `projects.scope_all` reads all project scope but cannot mutate without action permission.
- Custom role with action permission but no project membership cannot access project resources.
- Read-only custom role cannot POST.
- SUPER_ADMIN behavior unchanged.
- Existing ADMIN/VIEWER/PROJECT_MANAGER/REPORTER tests pass.
- No DB grant reset.

## Commands

```bash
pytest -q tests/test_auth_permissions.py tests/test_rbac_navigation.py tests/test_three_layer_authorization.py tests/test_project_manager_permissions.py -vv
PYTHONWARNINGS=error pytest -q -ra
python -m compileall -q app tests migrations
npm test
pip check
flask security-audit
git diff --check
```

Run permission sync on local DB only after reviewing dry result/current CLI semantics:

```bash
flask sync-permissions --apply-defaults
```

Do not use `--reset-defaults` unless explicitly approved.

## Definition of Done

- Custom roles can be built from new permissions.
- Scope_all works without granting mutations.
- Existing access unchanged except intended permission support.
- Full suite pass.

## Commit

```bash
git add app/permissions app/auth app/navigation.py app/templates/admin/roles tests docs/Phase9
# add exact migration only if schema genuinely required; normally none
git commit -m "feat(rbac): add Phase 9 permissions and custom-role access"
```
