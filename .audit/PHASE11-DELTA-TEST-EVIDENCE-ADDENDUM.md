# Phụ lục — bằng chứng test của delta audit Phase 11

Phụ lục bổ sung cho `PHASE11-DELTA-CLOSURE.md`. **Không sửa file closure đó**, vì nó
là hồ sơ đã chốt; đây là bản đính kèm ghi lại một kết luận đo lường sai đã được
làm rõ sau đó.

## Điều cần sửa

`PHASE11-DELTA-CLOSURE.md` ghi phần bằng chứng test là **chưa hoàn tất**, với lý do
hai lượt `pytest` rộng "bị môi trường dừng trước khi có summary".

Kết luận đó là **hiện tượng của giới hạn thời gian, không phải của lỗi trong code**.
Không có test nào treo và không có test nào đỏ.

## Nguyên nhân thật

Lượt chạy bị cắt ở 60 giây, trong khi suite cần khoảng 5 phút. Ở mốc 60 giây pytest
mới đi được khoảng 9%, và vì `-v` in tên test **trước** khi chạy, test cuối cùng hiện
trên màn hình lúc bị cắt trông như đang treo.

Cùng nguyên nhân này về sau lại gây chẩn đoán sai một lần nữa ở Bước 0 của Phase 12,
với đúng test bị nghi oan:
`tests/test_company_media_phase4_idempotency.py::test_selection_presign_conflict_creates_no_extra_rows_or_counter[changed2]`.

## Bằng chứng

Chạy trên nhánh `Phase12/Progress-and-beyond` tại commit `4497031`, là commit chỉ thêm
tài liệu và hồ sơ audit (10 file, không có file ứng dụng nào) — nên trạng thái code
ứng dụng đúng bằng trạng thái cuối của delta Phase 11:

```
473 passed, 3 skipped in 302.99s (0:05:02)
real	5m11,201s
```

Kiểm chứng riêng test bị nghi treo:

```
tests/test_company_media_phase4_idempotency.py::…[changed2]   1 passed in 0.78s
tests/test_company_media_phase4_idempotency.py (cả file)      8 passed in 5.29s
```

Tổng số test thu thập được ở thời điểm đó: 476 (473 pass + 3 skip).

## Ba test skipped là gì

Không phải khoảng trống mới phát sinh trong Phase 11. Cả ba là test PostgreSQL thật,
cố ý mở bằng biến môi trường và skip khi chưa cấu hình:

```
tests/test_company_media_phase4_postgresql.py:69  set PHASE4_POSTGRES_URL to run real PostgreSQL Phase 4 concurrency tests
tests/test_company_media_phase5_postgresql.py:69  set PHASE5_POSTGRES_URL after upgrading the disposable PostgreSQL database
tests/test_company_media_phase5_postgresql.py:93  set PHASE5_POSTGRES_URL after upgrading the disposable PostgreSQL database
```

## Kết luận

Bằng chứng test của delta audit Phase 11 là **đầy đủ và xanh**. Không có finding nào
phát sinh từ mục này. Phần "chưa hoàn tất" trong closure nên được đọc kèm phụ lục này.

Giới hạn vẫn còn nguyên giá trị: suite chạy trên SQLite in-memory với
`db.create_all()` (`tests/conftest.py:42`), nên nó **không** chứng minh hành vi
PostgreSQL dưới tải đồng thời, cũng không chứng minh migration Alembic — hai điều
này phải kiểm riêng.

## Khuyến nghị vận hành

Cấp cho mọi lượt `pytest` đầy đủ ít nhất 20 phút. Trước khi kết luận một test treo,
chạy riêng nó bằng `pytest -q "<nodeid>"`: nếu nó pass trong vài giây thì nó không
treo. Cân nhắc thêm `pytest-timeout` vào môi trường dev để test treo thật sẽ fail
kèm stack trace thay vì làm cả suite mất summary.
