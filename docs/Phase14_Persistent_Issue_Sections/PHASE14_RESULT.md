# Phase 14 — Kết quả hạng mục vấn đề tồn đọng

Ngày chốt: 2026-08-05  
Migrations: `20260805_0033_persistent_issue_sections` và
`20260805_0034_drop_persistent_issue_owner`

## 1. Kết quả theo từng bước đã nghiệm thu

| Bước | Việc đã làm | Chứng cứ | Test toàn suite |
| --- | --- | --- | --- |
| 1 | Thêm bảng `persistent_issue_sections`, quan hệ/model, migration chuyển dữ liệu cũ thành hạng mục và ràng buộc một loại hạng mục một lần. | Migration `20260805_0033_persistent_issue_sections`; model và test migration/chuyển đổi. | **750 passed, 3 skipped** |
| 2 | Thêm tính lại rollup, kiểm `due_date`/`closed_date`, và `scripts/verify_issue_rollup.py` để kiểm bất biến trên dữ liệu development. | `app/issues/services.py`, `scripts/verify_issue_rollup.py`, `tests/test_issue_rollup.py`. | **769 passed, 3 skipped** |
| 3 | Thay biểu mẫu phẳng bằng hạng mục tạo/sửa ở cả hai lối vào; mỗi hạng mục có loại, mức độ, trạng thái, hạn, người phụ trách, mô tả và đề xuất. | `app/templates/issues/form.html`, service/routing biểu mẫu và test section forms. | **778 passed, 3 skipped** |
| 3.1 | Sửa quy tắc tổng hợp để phân biệt `RESOLVED` với `CLOSED`: chỉ mọi hạng mục `CLOSED` mới đóng vấn đề. Tính lại dữ liệu development và script bất biến sạch. | Năm nhánh trong `recalculate_issue_rollup()` và bản cài đặt độc lập `expected_rollup()`. | **782 passed, 3 skipped** |
| 4 | Hiện rollup chỉ đọc trong biểu mẫu sửa; dọn danh sách, bỏ owner cấp vấn đề, thêm ngày đóng/số hạng mục; bỏ cột và quan hệ `PersistentIssue.owner_user_id`. Sửa migration SQLite bằng batch alter. | Migration `20260805_0034_drop_persistent_issue_owner`, biểu mẫu/danh sách/dashboard và test migration SQLite. Snapshot `issue.update` mới không còn `owner_user_id`; hàng audit cũ giữ snapshot lịch sử cũ, đúng theo hình dạng dữ liệu lúc ghi. | **788 passed, 3 skipped** |
| 5 | Bỏ close/reopen ở cấp vấn đề; giữ capability/permission cũ để gác chuyển vào/ra `CLOSED` ở hạng mục; thêm audit action cấp hạng mục. | `tests/test_issue_section_actions.py`, `tests/test_audit_groups.py`; route cũ trả 404. Rollup tự đóng không sinh audit vì đó là hệ quả, hành động thật là đóng hạng mục cuối. | **797 passed, 3 skipped** |
| 6 | Gộp lọc chung, thêm năm tiêu chí URL-backed, mặc định ẩn `CLOSED`, dùng `EXISTS` cho điều kiện hạng mục và phân trang 20 dòng ở hai danh sách. | `tests/test_issue_filters.py`, macro phân trang dùng chung và test phạm vi quyền/N+1 logic. | **808 passed, 3 skipped** |
| 6.1 | Sửa nhãn/icon của hạng mục sinh bằng JavaScript; server truyền payload nhãn và icon, đồng thời kiểm nội dung thật thay vì chỉ đếm option. | `tests_js/persistent-issue-sections.test.js`, `tests/test_issue_section_forms.py`. | **809 passed, 3 skipped** |

Toàn suite JavaScript ở mốc chốt có **41 test**, đều xanh.

## 2. Migration: SQLite cũng là lưới an toàn bắt buộc

Khẳng định cũ rằng “test không chạy migration” là **sai**. Có đúng một test chạy toàn bộ chuỗi
migration trên SQLite:
`tests/test_security_hardening.py::test_reset_local_dev_runs_migrations_and_seeds_admin`.

Đó là test duy nhất bắt lỗi Bước 4: `DROP COLUMN owner_user_id` trên SQLite để lại định nghĩa khoá
ngoại tham chiếu cột đã mất, khiến `flask reset-local-dev` tạo database hỏng. Sửa đúng là dùng
`op.batch_alter_table` cho cả upgrade và downgrade.

Đây là chiều ngược của cảnh báo lặp lại trong hai phase: không chỉ SQLite không chứng minh được
PostgreSQL; PostgreSQL cũng không chứng minh được SQLite. Upgrade và downgrade đã sạch trên
PostgreSQL nhưng vẫn không lộ lỗi SQLite này. Từ các phase sau, **mọi migration phải chạy test trên
trước khi báo hoàn tất**, kể cả khi đã xác minh PostgreSQL.

## 3. Ba lỗi chỉ mắt người mới thấy

Không lỗi nào dưới đây xuất hiện trong 809 test Python hay 41 test JavaScript:

- Quy tắc từng coi `RESOLVED` là trạng thái kết thúc. Code làm đúng đặc tả cũ, nhưng đặc tả sai
  so với nghiệp vụ; lỗi lộ ra ở cổng dừng thủ công.
- `closed_date` được lưu đúng nhưng không hiện ở đâu vì đặc tả danh sách quên cột này.
- Hạng mục sinh bằng JavaScript hiện enum tiếng Anh và thiếu icon. Toàn bộ 39 test JS khi đó vẫn
  xanh vì chúng đếm `<option>` thay vì đọc nhãn.

Bài học cho test JS: phải khẳng định nội dung thật, đồng thời có assertion phủ định để enum thô
không được xuất hiện.

## 4. Mười lần dừng-và-báo đều đúng

1. Grep tìm `@bp.route` bỏ sót `@bp.post` — sai dữ kiện.
2. Cột được nêu trong đặc tả không tồn tại — sai dữ kiện.
3. Bộ lọc được nói là có nhưng không có giao diện — sai dữ kiện.
4. Hàm sidebar được xem như đang hoạt động thực ra là code chết — sai dữ kiện.
5. Thiếu lối vào thứ hai trong blueprint dự án — phạm vi chưa đủ.
6. Chia bước sai: Bước 1 vừa cấm sửa một file vừa buộc bỏ cột mà chính file đó dùng — phạm vi chưa đủ.
7. Thiếu bề mặt thứ tư là dashboard dự án — phạm vi chưa đủ.
8. Thiếu capability `can_close_reopen_issues` — phạm vi chưa đủ.
9. Thiếu permission code `issues.close` — phạm vi chưa đủ.
10. Giả định danh sách đã có phân trang — phạm vi chưa đủ.

Cùng một gốc: đặc tả được viết từ mô hình trong đầu thay vì từ việc đọc hệ thống. Cách chữa đã
được chứng minh ở Bước 5: grep từ từng ký hiệu ra trước rồi mới viết phạm vi. Bước 5 là bước duy
nhất trong hai phase không cần dừng vì phạm vi thiếu.

## 5. Giới hạn đã biết

- Suite dùng SQLite in-memory và Python 3.10, không phải PostgreSQL và Python 3.12 production.
  Chưa chứng minh được ràng buộc `uq_persistent_issue_sections_issue_category` dưới hai request
  đồng thời, cũng như `recalculate_issue_rollup()` khi hai người cùng sửa hai hạng mục của một vấn
  đề, dù PostgreSQL path đã dùng `with_for_update()`.
- `scripts/verify_issue_rollup.py` chỉ kiểm hai vấn đề trên dữ liệu development; bằng chứng dữ liệu
  thật còn mỏng, phần nặng nằm ở unit test.
- `expected_rollup()` trong script là bản cài đặt **độc lập** của quy tắc §2.1 để bắt cả bug trong
  production. Đổi quy tắc phải sửa hai chỗ; không được xoá sự độc lập này.

## 6. Triển khai bắt buộc

Sau deploy chạy:

```text
flask db upgrade
```

Phase này có hai migration: `20260805_0033` và `20260805_0034`. Không cần chạy
`flask sync-permissions`: Phase 14 không thêm permission code, chỉ đổi nơi ba capability/permission
đã tồn tại có tác dụng.

## 7. Việc đã ghi lại, chưa làm

Chip đã ghi trước đó: tách thêm logic dùng chung giữa hai blueprint vấn đề. Việc này được hoãn có
chủ ý; refactor dưới chân công việc đang chạy tạo xung đột đắt hơn phần sao chép còn lại.
