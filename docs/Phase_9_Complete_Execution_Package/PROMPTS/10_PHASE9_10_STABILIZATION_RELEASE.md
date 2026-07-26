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
