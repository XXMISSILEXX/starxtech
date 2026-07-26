# PostgreSQL migration rehearsal

## Backup local/source database

Thay đường dẫn bằng thư mục bảo mật phù hợp:

```bash
mkdir -p ~/backups/starx-phase9
pg_dump "${DATABASE_URL/postgresql+psycopg:/postgresql:}" \
  --format=custom \
  --file="$HOME/backups/starx-phase9/pre-phase9-$(date +%Y%m%d-%H%M%S).dump"
```

Không commit backup.

## Copy database rehearsal

Thực hiện theo quyền PostgreSQL hiện có. Không chạy trên production khi chưa có owner approval.

Rehearsal phải kiểm tra:

1. Restore backup vào DB tạm.
2. Chạy migration từ baseline đến head.
3. Chạy data profile/constraints.
4. Chạy app/test với DB tạm.
5. Kiểm tra existing reports, sections, attachments, roles/grants.
6. Đo thời gian migration.
7. Thử rollback code với schema additive còn nguyên.

## Không làm

- Không downgrade destructive trên production.
- Không drop column/table mới khi đã có user data.
- Không backfill Customer bằng suy đoán ngoài mapping được owner chấp thuận, ngoại trừ nhóm “Chưa phân loại”.
