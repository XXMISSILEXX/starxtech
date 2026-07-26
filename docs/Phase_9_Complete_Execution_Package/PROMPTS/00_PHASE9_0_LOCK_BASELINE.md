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
