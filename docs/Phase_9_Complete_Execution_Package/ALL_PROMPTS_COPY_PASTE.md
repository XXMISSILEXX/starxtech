# ALL PHASE 9 PROMPTS — COPY/PASTE
Thực hiện tuần tự. Không gửi tất cả cùng lúc cho Codex.


---

# 00_PHASE9_0_LOCK_BASELINE

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


# STEP 9.0 — Khóa baseline và quyết định triển khai

## Mục tiêu

Tạo source-of-truth docs trong repo trước khi migration đầu tiên. Không thay đổi production behavior.

## Công việc

1. Xác minh audit với source hiện tại:
   - Project/ProjectUser/ReportCategory;
   - permission registry/DB grants;
   - Daily Report V2 endpoints;
   - PersistentIssue độc lập;
   - current dashboard aggregates;
   - navigation active module.
2. Tạo `docs/Phase9/` gồm:
   - `00_BASELINE.md`
   - `01_FINAL_DECISIONS.md`
   - `02_TARGET_DOMAIN.md`
   - `03_PERMISSION_CATALOGUE.md`
   - `04_MIGRATION_MAP.md`
   - `05_ROUTE_MAP.md`
   - `06_TEST_MATRIX.md`
   - `07_RELEASE_GATES.md`
3. Copy/translate chính xác các quyết định đã khóa từ package. Không phục hồi các đề xuất health/issue observation cũ trong audit.
4. Inventory exact existing permission codes và đánh dấu code mới dự kiến.
5. Inventory custom/legacy roles trong DB read-only; không reset defaults.
6. Chạy full baseline gate và lưu output không secret vào `docs/Phase9/evidence/`.

## Không làm

- Không model/migration/route/template behavior change.
- Không sync permission DB.
- Không sửa test expectation.

## Commands

```bash
source .venv/bin/activate
python -m compileall -q app tests migrations
npm test
PYTHONWARNINGS=error pytest -q -ra
pip check
flask db current
flask db heads
flask security-audit
git diff --check
```

## Definition of Done

- Docs phản ánh source hiện tại và decisions mới.
- Full suite 0 failed.
- Current=head.
- Chỉ docs Phase9 thay đổi.
- Không secret.

## Commit

```bash
git add docs/Phase9
git commit -m "docs(phase9): lock scope decisions and baseline"
```

## Báo cáo cuối

Nêu exact counts tests, branch/head, migration, roles/permissions inventory, file created, commit hash và xác nhận chưa thay đổi app behavior.


---

# 01_PHASE9_1_RBAC_CUSTOM_ROLES

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


---

# 02_PHASE9_2_CUSTOMERS_PROJECTS

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


---

# 03_PHASE9_3_CONTRACTORS_ASSIGNMENTS

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


---

# 04_PHASE9_4_PROJECT_UPDATES

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


---

# 05_PHASE9_5_PROJECT_OPERATIONS_UI

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


---

# 06_PHASE9_6_TODAY_NAV_CONFIG_REPORTS

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


---

# 07_PHASE9_7_DASHBOARD_CORE_PROJECT

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


---

# 08_PHASE9_8_CUSTOMER_SYSTEM_DASHBOARDS

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


---

# 09_PHASE9_9_CONTRACTOR_DASHBOARD

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


---

# 10_PHASE9_10_STABILIZATION_RELEASE

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


# STEP 9.10 — Stabilization, migration rehearsal và release

## Mục tiêu

Không thêm feature lớn. Đóng Phase 9 bằng data integrity, performance, security, migration rehearsal, manual acceptance và docs.

## Audit final

1. Model/constraint/index inventory.
2. Route/permission matrix.
3. Navigation custom-role matrix.
4. DB profile:
   - Customer/project classification;
   - contractor/assignment duplicates;
   - cross-project update FK impossible;
   - orphan rows;
   - report/category/attachment integrity.
5. Query performance dashboard.
6. Route compatibility/bookmarks.
7. No Partner-module coupling.
8. No forbidden models/fields:
   - health_status;
   - observation;
   - open issue;
   - ProjectReportItem.

## Migration rehearsal

Use `RUNBOOKS/MIGRATION_REHEARSAL.md`:

- backup;
- restore copy;
- baseline → head;
- validate data;
- app/test on copy;
- timing/rollback plan.

## Automated gate

```bash
python -m compileall -q app tests migrations
npm run build:heic-preview
npm test
find app/static/js -type f -name '*.js' -print0 | xargs -0 -n1 node --check
PYTHONWARNINGS=error pytest -q -ra
pip check
flask db current
flask db heads
flask security-audit
git diff --check
```

Runtime:

```bash
redis-cli -n 0 ping
curl -fsS http://192.168.1.159:9000/minio/health/live >/dev/null
python -m celery -A app.celery_worker:celery_app inspect ping --timeout=5
```

## Manual acceptance

Use `CHECKLISTS/MANUAL_ACCEPTANCE.md`.

Mandatory:

- Chrome desktop;
- iPhone Safari;
- custom roles/direct URL;
- Customer/project accordion;
- contractor assignment/update;
- VTS handover example;
- Today submitted/missing;
- Daily Report JPG/HEIC/S3/Celery regression;
- all dashboards/counts;
- archived/ended history.

## Docs

Create/update:

```text
docs/Phase9/PHASE9_ACCEPTANCE.md
docs/Phase9/PHASE9_MIGRATION_RUNBOOK.md
docs/Phase9/PHASE9_RBAC_MATRIX.md
docs/Phase9/PHASE9_USER_GUIDE.md
docs/Phase9/PHASE9_RELEASE_NOTES.md
```

Do not write PASS for untested items.

## Release decision

Only close Phase 9 when:

- full suite 0 failed;
- DB current=head;
- migration rehearsal PASS;
- security/runtime PASS;
- desktop/iPhone PASS;
- acceptance signed;
- no unresolved blocking issue.

## Commit

```bash
git add <explicit-final-files>
git commit -m "chore(release): stabilize and document Phase 9"
```

Then show branch log and propose merge; do not merge/push without user instruction.
