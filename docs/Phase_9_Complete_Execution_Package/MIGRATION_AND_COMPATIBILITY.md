# Migration và compatibility

## Nguyên tắc

1. Backup trước migration schema đầu tiên.
2. Rehearse trên PostgreSQL copy.
3. Additive, nullable trước.
4. App code dual-read khi cần.
5. Backfill có dry-run/report.
6. Validate dữ liệu.
7. Constraint sau khi sạch.
8. Không destructive downgrade trong production.

## Migration sequence đề xuất

### M1 — Customer

- create `customers`;
- add nullable `projects.customer_id`;
- add indexes;
- create/backfill “Khách hàng chưa phân loại”.

### M2 — Contractors

- create `project_contractors`;
- create `project_contractor_assignments`;
- role/status constraints/indexes.

### M3 — Project updates

- create `project_updates`;
- optional assignment FK;
- soft-delete/index project/date/assignment.

### M4 — Daily Report category safety, chỉ khi step 9.6

- nullable category name/icon snapshots;
- no status migration.

## Compatibility

- Existing project without customer must still render until backfill complete.
- Existing DailyReport and attachments untouched.
- Existing category FK remains.
- Existing PersistentIssue untouched.
- Existing Reports routes stay operational or redirect tested.
- Existing RBAC DB grants must not be reset accidentally.

## Rollback

- Disable feature routes/navigation.
- Revert code while leaving additive tables/nullable columns.
- Do not delete new domain data automatically.
- Restore backup only after explicit failure analysis.
