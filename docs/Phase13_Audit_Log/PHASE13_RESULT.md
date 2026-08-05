# Phase 13 — Kết quả audit log

Ngày chốt: 2026-08-04  
Migration: `20260804_0032_audit_log_indexes` (bốn index cho trang đọc)

## 1. Kết quả theo từng bước đã nghiệm thu

| Bước | Việc đã làm | Chứng cứ | Test toàn suite |
| --- | --- | --- | --- |
| Bước 2c | Hoàn tất snapshot cho các thao tác phá huỷ: bản ghi xoá/archival giữ đủ dữ liệu điều tra thay vì chỉ giữ khoá ngoại; bao gồm attachment, báo cáo, đối tác, khách hàng, cập nhật dự án và cấu trúc tiến độ. | Commit `d341bd5`; các kiểm thử snapshot ở `tests/test_phase13_audit_snapshots.py`, cùng các test của reports, admin, customers, partners và progress. | **642 passed, 3 skipped** |
| Bước 3 | Đặt bộ phân loại action vào `app/audit.py`; ngừng emitter cho create của nội dung khi bản ghi nghiệp vụ đã tự lưu người tạo/thời điểm tạo; giữ các action create cần thiết cho trách nhiệm giải trình. | Commit `89d0ff2`; `tests/test_audit_groups.py`; `LEGACY_CONTENT_CREATE_ACTIONS` và test xác nhận emitter đã tắt. | **729 passed, 3 skipped** |
| Bước 4 | Thêm bốn index phục vụ bốn hình dạng truy vấn của audit reader: thời gian, action + thời gian, actor + thời gian, và entity type/id. | Commit `288ec09`; migration `20260804_0032_audit_log_indexes.py`; `tests/test_audit_log_indexes.py`. | **730 passed, 3 skipped** |
| Bước 5 | Ghi audit cho tải file gốc, tải media gốc và mỗi lượt tải hàng loạt; không ghi preview/thumbnail. | Commit `62cd699`; test tại company media, project documents, bulk download và security hardening. | **733 passed, 3 skipped** |
| Bước 6 | Hoàn tất blueprint chỉ đọc `audit_log`, trang danh sách/chi tiết, lọc URL, phân trang SQL, che khoá nhạy cảm và permission `audit_logs.view`. | `app/audit_log/`, `app/templates/audit_log/`, `tests/test_audit_log_views.py`; route mutation không tồn tại và các phương thức ghi trả 405. | **738 passed, 3 skipped** |
| Bước 6.1 | Hoàn tất nối quyền quản trị: cổng vào admin, redirect, registry/default và sidebar desktop/mobile cùng nhận biết audit log. | Các thay đổi ở `app/auth/permissions.py`, `app/modules/routes.py`, `app/permissions/registry.py`, `app/templates/base.html`; ma trận route/sidebar trong `tests/test_audit_log_views.py`. | **741 passed, 3 skipped in 7:01** |

Mỗi mốc trên đã chạy lại toàn bộ suite trong một lượt độc lập. Bước 0 trước triển khai được lưu ở `BASELINE_13.md`: **629 passed, 3 skipped**; JavaScript: 9 file test, 36 khai báo test, đều pass.

## 2. Module gate và bốn điểm phải sửa khi thêm màn hình quản trị

Đã đọc `require_reports_module_access` tại `app/__init__.py:189-209`. Tuple `report_endpoints` chỉ gồm chín tiền tố: `dashboard.`, `dashboard_api.`, `projects.`, `reports.`, `issues.`, `attachments.`, `customers.`, `project_operations.`, `construction_progress.`; cộng tập khớp chính xác gồm 11 endpoint admin. **Không có tiền tố `"admin."`.** Vì vậy blueprint `audit_log.` đi xuyên qua hook này. Nó không có một “module gate” báo cáo; các gác thực sự là `require_login` và `permission_required("audit_logs.view")` tại từng route. Đây là chủ ý kiến trúc cần ghi thẳng để người sau không đi tìm một module gate không tồn tại.

Thêm một màn hình quản trị mã hoá cùng một câu hỏi — “ai được vào khu vực quản trị” — tại bốn nơi độc lập. Chúng không biết nhau; bỏ sót mỗi nơi tạo một kiểu lỗi khác nhau:

| Chỗ | Hậu quả nếu quên |
| --- | --- |
| `can_access_admin_module()` — `app/auth/permissions.py` | Không vào được khu vực quản trị. |
| Chuỗi redirect `select_admin()` — `app/modules/routes.py` | `abort(403)` dù đã qua cổng. |
| Hàm sinh `VIEWER_ADMIN` — `app/permissions/registry.py` | **Tự cấp** quyền ngoài ý muốn. |
| Điều kiện `or` sidebar mobile — `app/templates/base.html` | Có link trên desktop, nhưng mất toàn bộ khối quản trị trên điện thoại. |

Trong Phase 13, bốn điểm này được tìm ra lần lượt; ba điểm cuối chỉ lộ ra sau khi đã viết code. Đã ghi một task riêng để thêm test chống lệch bốn điểm này cho mọi màn hình quản trị mới.

## 3. Quyết định phân quyền

Chủ dự án chốt mặc định **chỉ `ADMIN`** được xem audit log. Mọi vai khác, kể cả `VIEWER_ADMIN`, phải có grant tường minh. Đây không phải chi tiết UI: `audit_logs.view` có `action == "view"`, nên hàm sinh preset ở `registry.py` sẽ tự cấp nó cho `VIEWER_ADMIN` nếu không loại trừ tường minh. Vì thế “không thêm vào VIEWER_ADMIN” là không đủ; phải thêm ngoại lệ loại trừ.

Test then chốt xác nhận `VIEWER_ADMIN` mặc định nhận **403**. Một vai chuyên biệt vẫn có thể nhận `audit_logs.view` tường minh, vào được khu vực quản trị và chỉ thấy liên kết audit của mình.

## 4. Nhóm action và retention

| Nhóm | Ý nghĩa | Giữ |
| --- | --- | --- |
| `destructive` | Xoá, archive, restore, deactivate | Vĩnh viễn |
| `authority` | Quyền, vai trò, membership, chia sẻ | Vĩnh viễn |
| `mutation` | Sửa dữ liệu nghiệp vụ | Vĩnh viễn |
| `security` | Đăng nhập thất bại và hành động CLI bảo mật | Vĩnh viễn |
| `disclosure` | Tải bản gốc và tải hàng loạt | 24 tháng |
| `retain_forever` | Fallback an toàn cho action chưa biết | Vĩnh viễn |

Bộ phân loại có ba tầng theo thứ tự bắt buộc: (1) ngoại lệ khai báo tường minh, (2) luật hậu tố, (3) fallback `retain_forever`. Không được đảo thứ tự: nếu luật hậu tố chạy trước, `project_membership.update` sẽ bị xếp nhầm thành `mutation`, còn `user.reset_password` sẽ rơi vào fallback thay vì ngoại lệ `authority`.

Toàn bộ **80 action lịch sử** đã được phân loại tường minh, không action nào rơi vào fallback. Fallback vẫn tồn tại để action tương lai được giữ an toàn thay vì vô tình bị đưa vào chính sách xoá.

### Dữ liệu create lịch sử không bị xoá

**820 hàng tạo nội dung lịch sử vẫn nằm nguyên trong `audit_logs`.** Emitter đã được tắt; đối chiếu database development xác nhận mọi hàng `.create` nội dung mới nhất đều trước mốc commit Bước 3, `2026-08-04 14:35:27`. Các hàng này chỉ bị ẩn ở tầng xem thông qua `LEGACY_CONTENT_CREATE_ACTIONS`, không bị DELETE và cũng không bị chỉnh sửa.

Nếu sau này thực hiện retention thật, mọi thao tác xoá phải tự ghi một audit record cho biết đã xoá bao nhiêu hàng và khoảng thời gian nào. Một audit log xoá được mà không để lại dấu vết thì không còn là audit log. Logic retention chưa thuộc Phase 13; khi làm cần idempotent, xoá theo lô và tránh lock bảng lâu.

### Không nhân đôi `download_events`

`download_events` đã có **3.121 hàng** lịch sử tải file và `admin_storage` có màn hình Dung lượng & băng thông riêng. Nhóm `disclosure` của audit log bắt đầu gần như rỗng vì emitter chỉ xuất hiện từ Bước 5, và nhóm này còn bị loại khỏi khung nhìn mặc định đầu tiên.

Câu hỏi “ai đã tải gì trước tháng 8/2026” phải hỏi màn hình Dung lượng & băng thông, không phải audit log. Audit log chỉ bổ sung `ip_address`, `user_agent` và tham chiếu đối tượng nghiệp vụ cho các lượt tải mới; nó không thay thế lịch sử `download_events`.

## 5. Giới hạn quy mô đã biết

- Khi `audit_logs` đạt khoảng nửa triệu hàng, thêm index phải dùng `CREATE INDEX CONCURRENTLY` ngoài transaction, tức là một migration khác hẳn. Migration Phase 13 dùng `CREATE INDEX` thường vì bảng hiện khoảng 1.270 hàng.
- Macro phân trang cũ duyệt toàn bộ số trang trong vòng lặp Jinja rồi mới lọc. Ở 63 trang không đáng kể, nhưng nửa triệu hàng sẽ thành khoảng 25.000 vòng lặp mỗi render. Cách sửa là tính danh sách trang cần hiện ở Python.
- SQL `NULL` không xuất hiện ở hai cột JSON qua đường ghi bình thường: `JSON` của SQLAlchemy mặc định `none_as_null=False`, nên `old_values=None` được lưu thành JSON `null`. Template vẫn xử lý đủ object, JSON `null` và SQL `NULL`, vì dữ liệu lịch sử hoặc SQL trực tiếp có thể tạo đủ ba trạng thái.

## 6. Triển khai bắt buộc

Sau deploy, phải chạy **cả hai** lệnh:

```text
flask db upgrade
flask sync-permissions --apply-defaults
```

Lệnh đầu cài bốn index của Bước 4. Lệnh sau tạo permission `audit_logs.view` và grant mặc định cho `ADMIN`.

Lệnh thứ hai đặc biệt dễ bị quên: kiểm database development sau Bước 6 cho thấy `audit_logs.view` chưa có trong bảng `permissions` — **0 hàng, 0 grant**. Trang vẫn mở với tài khoản thử vì tài khoản đó là `SUPER_ADMIN`, vai này bypass mọi kiểm tra quyền. Một người dùng `ADMIN` thật sẽ nhận **403**. Hệ thống không tự đồng bộ permission lúc khởi động; đó là quyết định có chủ ý, đã ghi trong `CLAUDE.md`.

## 7. Việc đã ghi lại, chưa làm

Sáu việc phát hiện trong phase này đã được tạo task riêng, không thuộc Phase 13:

1. Xoá khối `attachment.delete` chết trong `app/reports/services.py` sau một `return`.
2. Gán `created_by_user_id` khi tạo dự án: cột tồn tại nhưng không nơi nào gán, nên `project.create` đang là dấu vết duy nhất.
3. Khai báo 9 index biểu thức/index có điều kiện vào metadata; autogenerate hiện muốn xoá chúng, trong đó **2 index UNIQUE** chặn trùng tên album và trùng tên thư mục.
4. Xoá 2 decorator quyền chết trong `app/auth/permissions.py`; một decorator tên `super_admin_required` nhưng thực tế nhận cả `ADMIN`.
5. Xoá hoặc nối dây `get_sidebar_items()`; hàm đang được inject vào mọi template nhưng không template nào dùng, khiến nó trông như cơ chế sidebar thật.
6. Viết test chống lệch cho bốn chỗ phân quyền quản trị ở mục 2.

## 8. Test tay còn lại

Các việc sau chưa được xác minh tự động vì suite chạy SQLite với `FakeStorageProvider`:

1. Đăng nhập bằng một `ADMIN` thật, không phải `SUPER_ADMIN`.
2. Xem sidebar ở bố cục mobile.
3. Bấm qua các trang giữa của danh sách và xác nhận mọi bộ lọc còn nguyên.
4. Mở chi tiết một hàng `attachment.delete` và xác nhận `object_key` hiển thị nguyên.

## 9. Các điểm đặc tả gốc đã sai và đã sửa

Tài liệu phải ghi lại cả sai sót để lần sau còn đáng tin: `issues` đã có sẵn route close/reopen/delete, không phải chức năng cần xây mới; `download_events` không được đặc tả ban đầu nhắc tới nhưng là nguồn lịch sử tải file cần giữ riêng; `project.create` phải giữ lại vì `created_by_user_id` hiện không được gán; và quyền vào khu vực quản trị thực tế nằm ở bốn chỗ độc lập nêu tại mục 2, không phải một module gate duy nhất.
