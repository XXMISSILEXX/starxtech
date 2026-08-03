# Phase 12.4 — Dashboard tiến độ

Vòng sửa tiếp sau Phase 12.3. Đọc `CLAUDE.md` trước.
Đặc tả gốc: `PHASE12_CONSTRUCTION_PROGRESS.md`. Ba vòng trước:
`PHASE12_1_UX_AND_HARD_DELETE.md`, `PHASE12_2_ENTRY_LIST_AND_OVERLAY_ERRORS.md`,
`PHASE12_3_GANTT.md`.

Trạng thái: **chưa triển khai**. Nguồn yêu cầu: chủ dự án, sau khi đối chiếu với bảng
WBS thật của dự án An Bình.

---

## 0. Bối cảnh nghiệp vụ quyết định thiết kế

Bảng WBS thật của chủ dự án có cấu trúc: **giai đoạn → công việc chính → khu vực áp
dụng**, với mỗi giai đoạn mang mốc bắt đầu, mốc kết thúc, số ngày, phần trăm hoàn
thành và trạng thái.

Ánh xạ sang hệ thống:

| WBS | Hệ thống |
|---|---|
| Giai đoạn (ví dụ "1. THI CÔNG PHẦN THÔ") | `ProgressType` — loại tiến độ |
| Khu vực áp dụng | `ProgressGroup` — khu vực |
| Công việc chính | `ProgressItem` — hạng mục |

Hiện chỉ **giai đoạn 1** đã lên hệ thống; bốn giai đoạn còn lại sẽ được tạo sau. Mọi
màn hình phải hoạt động đúng khi chỉ có một giai đoạn và tự dài ra khi thêm giai đoạn,
không cần sửa code.

### Quyết định đã chốt

1. **Không có tiến độ tổng của dự án.** Không dòng tổng, không ô phần trăm ở cấp dự
   án. Lý do không phải thiếu thời gian mà là **chưa chốt cách cộng các giai đoạn**:
   trung bình đơn giản coi giai đoạn 20 ngày nặng bằng giai đoạn 40 ngày; trọng số
   theo số ngày phản ánh thời gian; trọng số theo dự toán phản ánh giá trị nhưng cần
   khai thêm dữ liệu. Khi nào cần, khuyến nghị dùng **trọng số theo số ngày** vì cột
   `Số ngày` đã có sẵn trong cách lập kế hoạch của chủ dự án.

2. **Không đặt phần trăm của một giai đoạn vào hàng ô số cấp dự án.** Một con số đúng
   đặt cạnh các số của cả dự án sẽ bị đọc thành phần trăm của dự án. Cùng loại lỗi với
   `937.000` ở Phase 12.1: số đúng, ngữ cảnh sai.

3. **Mốc kế hoạch của giai đoạn là giá trị dẫn xuất**, suy từ hạng mục đã khai ngày.
   Không thêm trường nhập tay ở cấp loại tiến độ. Hệ quả đã được chủ dự án chấp nhận:
   mốc trên dashboard là **tổng của phần đã khai**, nên có thể hẹp hơn mốc gốc trong
   WBS khi mới khai một phần. Đây là hệ quả có chủ ý, không phải lỗi.

4. **Dashboard tiến độ scope theo dự án người xem tiếp cận được**, KHÔNG đòi
   `projects.scope_all` như ba dashboard hệ thống/khách hàng/đối tác. Nhờ vậy một màn
   hình phục vụ cả ban lãnh đạo (thấy toàn bộ) và chỉ huy trưởng (thấy dự án của mình),
   không cần cấu hình thêm.

5. **Bốn dashboard hiện có: không sửa gì.** Cổng vào đã đúng và admin quản lý được qua
   trang vai trò; lọc nội dung theo capability đã được sửa ở commit `684f34a`. Mọi
   thay đổi là mở lại bề mặt đã mất bốn finding mới làm đúng.

---

## 1. Hàm suy diễn còn thiếu

Phase 12.3 đã có `item_gantt_timeline` và `group_gantt_timeline`
(`app/construction_progress/services.py:85` và `:108`), nhưng
`gantt_timeline_for_type` (`:125`) **chỉ gom danh sách khu vực**, không tính khoảng
ngày cho chính loại tiến độ. Hai cột "Kế hoạch" và "Số ngày" của dashboard chưa có
nguồn dữ liệu.

Thêm một hàm thuần, dùng đúng phép `min`/`max` đã viết ở dòng 118–119, cộng một tầng
nữa trên các khu vực:

```
type_progress_summary(progress_type, entries_by_item_id=None, *, today=None) -> {
    "progress_type":  <ProgressType>,
    "percent":        Decimal | None,          # đã có, dùng type_percent()
    "planned_start":  date | None,             # min trên các khu vực đã khai ngày
    "planned_end":    date | None,             # max trên các khu vực đã khai ngày
    "days":           int | None,              # (planned_end - planned_start).days + 1
    "status":         "not_started" | "in_progress" | "overdue" | "done",
    "overdue_items":  int,                     # số hạng mục quá hạn
    "undated_items":  int,                     # số hạng mục chưa khai ngày kế hoạch
    "last_entry_date": date | None,            # ngày phiếu muộn nhất trong loại
}
```

### Quy tắc suy diễn

**Khoảng kế hoạch**: `min`/`max` trên các khu vực có khoảng kế hoạch, tức các khu vực
có ít nhất một hạng mục đã khai ngày. Loại không có khu vực nào như vậy thì
`planned_start`, `planned_end`, `days` đều là `None`, và dashboard **để trống hai cột
đó** — không hiện `0` và không hiện `—/—`. Hành vi rỗng này đúng theo cấu trúc, không
cần điều kiện riêng.

**Số ngày** tính bao gồm cả hai đầu: `(planned_end - planned_start).days + 1`. Một
giai đoạn từ 01/08 đến 01/08 là 1 ngày, không phải 0.

**Trạng thái**, xét theo thứ tự này:

| Điều kiện | Trạng thái |
|---|---|
| `percent` là `None` hoặc chưa có hạng mục nào khai ngày | `not_started` |
| `percent >= 100` | `done` |
| `planned_end < today` và `percent < 100` | `overdue` |
| `planned_start <= today` | `in_progress` |
| còn lại | `not_started` |

Nhãn tiếng Việt: "Chưa bắt đầu", "Đang triển khai", "Quá hạn", "Hoàn thành" — đúng bốn
trạng thái chủ dự án đang ghi tay trong WBS.

**Hạng mục quá hạn**: `planned_end_date < today` và phần trăm hạng mục đó `< 100`.
Hạng mục chưa khai ngày **không** tính là quá hạn.

**Hạng mục chưa khai ngày**: dùng lại `excluded_items` mà `gantt_timeline_for_type` đã
tính, đừng đếm lại.

Hàm phải là **hàm thuần trên dữ liệu đã nạp**, không tự truy vấn, để test độc lập được
và để chỗ gọi kiểm soát việc nạp sẵn quan hệ.

---

## 2. Khối tiến độ trên dashboard dự án

Thêm vào dashboard dự án hiện có (`projects.dashboard`), **dưới** hàng bốn ô số đang có.

### Bốn ô số

Không ô nào là phần trăm — đây là điều kiện của quyết định 2.

| Ô | Giá trị |
|---|---|
| Giai đoạn đang chạy | `n / m` — số loại có trạng thái `in_progress` trên tổng số loại |
| Hạng mục quá hạn | tổng trên mọi giai đoạn |
| Chưa khai ngày | tổng trên mọi giai đoạn |
| Cập nhật gần nhất | ngày phiếu muộn nhất trong dự án, hoặc `—` |

### Bảng theo giai đoạn

Một dòng mỗi loại tiến độ, cột: Giai đoạn, Kế hoạch (`01/08 → 10/09/2026`), Số ngày,
Hoàn thành (thanh + số dùng `vn_number(places=1)`), Trạng thái (nhãn màu).

- Sắp xếp theo `planned_start` tăng dần; loại chưa có ngày xếp cuối theo tên.
- **Không có dòng tổng.**
- Liên kết "Xem tiến độ" sang `/projects/<id>/progress`.
- Trạng thái rỗng: dự án chưa có loại tiến độ nào thì hiện một dòng hướng dẫn tạo, không
  hiện bảng trống.

### Phân quyền — theo đúng khuôn `684f34a`

```python
include_progress = user_has_project_capability(current_user, project.id, "can_view_progress")
```

Không có quyền thì **cả khối biến mất**, không phải 403 và không phải bảng rỗng. Đây là
khuôn đã dùng cho `can_view_reports` và `can_view_issues` ở
`app/dashboard/services.py:142-185`; bám theo, không phát minh cách khác.

Không thêm capability mới. Không đổi cổng vào của `projects.dashboard`.

---

## 3. Card mới "Dashboard tiến độ thi công"

Màn hình riêng trong hub dashboard, xuyên nhiều dự án, để ban lãnh đạo xem mà không
phải vào chi tiết từng dự án.

### Phân quyền

- Permission code mới `dashboards.progress.view`, thêm vào `_RESOURCES` và `PERMISSIONS`
  trong `app/permissions/registry.py` theo mẫu bốn code `dashboards.*.view` hiện có.
- Thêm vào `DEFAULTS` cho `ADMIN` và `VIEWER_ADMIN` giống bốn code kia.
- **KHÔNG** đòi `projects.scope_all` (quyết định 4).
- Phạm vi dữ liệu: các dự án người xem tiếp cận được, giao với những dự án họ có
  `can_view_progress`. Người có `projects.scope_all` thấy toàn bộ.
- Thêm card vào `dashboard_navigation_context` (`app/dashboard/routes.py:133`) để nó
  xuất hiện trong lưới card của hub theo đúng cách bốn card kia đang làm.
- Kiểm tiền tố endpoint với `require_reports_module_access` trong `app/__init__.py`:
  route mới nằm dưới blueprint `dashboard` nên đã được gate, **xác nhận lại** chứ đừng
  giả định.

### Nội dung

Sắp xếp **theo vấn đề, không theo dự án** — người xem cần biết cái gì đang chậm, không
cần đọc theo thứ tự bảng chữ cái.

Dải bốn ô số ở đầu:

| Ô | Giá trị |
|---|---|
| Dự án có tiến độ | số dự án trong phạm vi có ít nhất một loại tiến độ |
| Giai đoạn quá hạn | tổng trên mọi dự án |
| Hạng mục quá hạn | tổng trên mọi dự án |
| Không cập nhật quá 7 ngày | số dự án có phiếu muộn nhất cách đây hơn 7 ngày, hoặc chưa có phiếu nào |

Bảng phẳng, một dòng mỗi cặp (dự án, giai đoạn): Dự án, Giai đoạn, Kế hoạch, Số ngày,
Hoàn thành, Trạng thái, và liên kết sang mô đun tiến độ của dự án đó.

Thứ tự: `overdue` trước, rồi `in_progress`, rồi `not_started`, rồi `done`; trong mỗi
nhóm xếp theo `planned_end` tăng dần. Phân trang khi quá 50 dòng.

Không có dòng tổng, không có phần trăm cấp dự án, không có phần trăm cấp toàn hệ thống.

---

## 4. Kế hoạch thi hành

Năm bước, mỗi bước một commit, mỗi commit `pytest` xanh toàn bộ.
**Ngân sách pytest ít nhất 20 phút.**

| Bước | Nội dung | Lý do xếp ở đây |
|---|---|---|
| 0 | Mốc xanh, ghi `BASELINE_12_4.md` | Không có mốc thì test đỏ sau này không quy được trách nhiệm |
| 1 | `type_progress_summary()` + test hàm thuần | Số phải đúng trước khi vẽ |
| 2 | Khối tiến độ trên dashboard dự án | Nhỏ hơn, trong ngữ cảnh sẵn có, kiểm được ngay trên dữ liệu thật |
| 3 | Card mới trong hub + permission code + navigation context | Bề mặt mới, cần đủ ba lớp phân quyền |
| 4 | Chốt: thêm mục mới vào cuối `PHASE12_RESULT.md` | |

Cổng dừng: sau **Bước 2** để chủ dự án xem khối trên dashboard dự án thật, và sau
**Bước 3** để xem card mới.

Bước 4 phải ghi **cả** commit `4bde515` (vòng trau nút và overlay) vì vòng đó đã làm
xong mà chưa có dòng nào trong `PHASE12_RESULT.md`.

### File được phép sửa

```
app/construction_progress/services.py        type_progress_summary
app/dashboard/services.py                    khối tiến độ cho dashboard dự án + dữ liệu card mới
app/dashboard/routes.py                      route card mới + navigation context
app/permissions/registry.py                  dashboards.progress.view + DEFAULTS
app/templates/dashboard/*.html               khối tiến độ + template card mới
tests/test_construction_progress_*.py
tests/test_dashboard_*.py
docs/.../BASELINE_12_4.md
docs/.../PHASE12_RESULT.md                   chỉ thêm mục mới ở cuối
```

Cấm chạm: `app/models/**` (vòng này **không đổi schema, không migration**),
`app/config.py`, `pytest.ini`, `app/auth/permissions.py`, `app/project_memberships.py`
(**không thêm capability mới**), `.audit/**`, bốn primitive
`project_read_required`/`project_write_required`/`project_manage_required`/`can_write_project`,
và cổng vào của bốn dashboard hiện có.

Nếu một bước có vẻ cần đổi schema hoặc thêm capability thì **DỪNG và báo** — nghĩa là
hiểu sai phạm vi.

### Kiểm thử bắt buộc

`type_progress_summary`, test như hàm thuần:

- Loại không có khu vực nào khai ngày → `planned_start`, `planned_end`, `days` đều
  `None`, trạng thái `not_started`.
- Loại có hai khu vực khai ngày → `planned_start` là min, `planned_end` là max, bỏ qua
  khu vực chưa khai.
- `days` bao gồm cả hai đầu: 01/08 đến 01/08 ra **1**.
- Bốn trạng thái, mỗi trạng thái một test: chưa bắt đầu, đang triển khai, quá hạn,
  hoàn thành.
- `percent >= 100` mà `planned_end` đã qua → `done`, **không** phải `overdue`.
- Hạng mục chưa khai ngày **không** tính vào `overdue_items`.
- `undated_items` khớp `excluded_items` của `gantt_timeline_for_type`.

Khối trên dashboard dự án:

- Có `can_view_progress` → khối hiện, bảng đúng số dòng, không có dòng tổng.
- **Không** có `can_view_progress` → khối **không có trong HTML**, và trang vẫn trả 200.
  Đây là assertion phủ định, viết cho đúng.
- Dự án chưa có loại tiến độ nào → hiện dòng hướng dẫn, không hiện bảng trống.
- Loại chưa khai ngày → hai cột Kế hoạch và Số ngày **để trống**, không hiện `0`.
- Không ô số nào trong hàng bốn ô là phần trăm.

Card mới:

- Ma trận 8 vai cho URL mới: chưa đăng nhập, thiếu module gate, thiếu
  `dashboards.progress.view`, có quyền nhưng không có dự án nào với `can_view_progress`,
  có quyền và có dự án, `VIEWER_ADMIN` chỉ đọc, `ADMIN`, `SUPER_ADMIN`.
- **Cách ly phạm vi**: dự án mà người xem không có `can_view_progress` **không xuất
  hiện**, kể cả khi họ đọc được dự án đó. Test với hai dự án và một người chỉ có quyền
  tiến độ ở một dự án.
- Card **không** xuất hiện trong lưới hub với người thiếu `dashboards.progress.view`.
- Thứ tự: quá hạn trước, rồi đang triển khai, rồi chưa bắt đầu, rồi hoàn thành.
- Phân trang bằng LIMIT/OFFSET ở tầng SQL nếu vượt 50 dòng, không cắt trong Python.
- Nạp sẵn quan hệ để tránh N+1: mỗi dòng cần tên dự án, tên loại, và số liệu tổng hợp.

Chốt: `grep -rnF '\x' tests/test_construction_progress_*.py tests/test_dashboard_*.py`
phải rỗng. Assertion tiếng Việt dùng `get_data(as_text=True)`. JS: dán cả
`grep -h '^test(' tests_js/*.test.js | wc -l` và khối tổng kết node.

Sau khi thêm permission code, ghi vào báo cáo rằng deploy cần
`flask sync-permissions --apply-defaults`. Vòng này **không** cần `flask db upgrade` vì
không có migration.

### Ngoài phạm vi

Tiến độ tổng của dự án và cách chọn trọng số (xem quyết định 1). Sửa bốn dashboard hiện
có (quyết định 5). Tạo một hạng mục cho nhiều khu vực cùng lúc — việc này đáng làm và
đã được ghi nhận, nhưng không thuộc vòng dashboard. Xuất báo cáo, so sánh nhiều kỳ,
biểu đồ trên dashboard tiến độ, và drill-down sâu hơn một liên kết sang mô đun.

---

## 5. Bổ sung — biểu đồ cột theo khu vực trên dashboard tiến độ

Yêu cầu thêm của chủ dự án sau khi nghiệm thu Bước 3: dashboard tiến độ cần chi tiết
hơn, có biểu đồ cột cho các khu vực của **một** giai đoạn, kèm bộ chọn giai đoạn.

### Dùng lại thứ đã có, không thêm gì mới

- Route `chart-data` (`app/construction_progress/routes.py:357`) đã trả về đúng dữ
  liệu: `labels` là tên khu vực, `percentages` là phần trăm từng khu vực,
  `overall_percent`, cộng `completed`/`remaining` khi `value_mode = money`. **Không sửa
  route này.** Đây là route đã được cố ý giữ lại ở Phase 12.2 cho đúng việc này.
- Khuôn vẽ chart trên dashboard đã có ở `app/static/js/scoped-dashboard-charts.js`:
  đọc URL từ một `data-*` attribute, `fetch` với `Accept: application/json`, rồi
  `new Chart(...)`. Bám khuôn đó, đừng phát minh cách khác.

### Bộ chọn giai đoạn

Bộ chọn phải chọn **cặp (dự án, giai đoạn)**, không phải chỉ giai đoạn — hai dự án có
thể có giai đoạn trùng tên. Nhãn dạng `001 · An Bình Homeland — THI CÔNG PHẦN THÔ`.

Cơ chế: form `GET` với tham số `?type_id=`, dropdown tự submit khi đổi — cùng cách bộ
lọc danh sách phiếu ở Phase 12.2 đang làm. Nhờ vậy lựa chọn nằm trong URL nên chia sẻ
được và bấm Back hoạt động đúng.

Danh sách trong dropdown **chỉ chứa các cặp trong phạm vi người xem** — đúng tập đã
dùng cho bảng, tức dự án tiếp cận được giao với dự án có `can_view_progress`.

**Mặc định**: giai đoạn ở dòng đầu của bảng đã sắp xếp, tức giai đoạn có vấn đề nhất
(`overdue` trước). Nhờ vậy biểu đồ có ích ngay khi mở, không cần bấm gì.

`type_id` không thuộc phạm vi người xem → xử lý như không tìm thấy, quay về mặc định
hoặc 404; chọn một cách và test nó. Không được dùng `type_id` để dựng tên template hay
tên thuộc tính.

### Biểu đồ

- Cột dọc, một cột mỗi khu vực, trục dọc là phần trăm hoàn thành 0–100.
- `value_mode = money` dùng cột xếp lớp `completed` và `remaining` như `chart-data` đã
  trả về.
- **Bọc canvas trong một div có chiều cao xác định và `position: relative`, cùng
  `maintainAspectRatio: false`.** Biểu đồ ở Phase 12 đã từng vỡ layout, cao vô hạn vì
  thiếu đúng hai thứ này — ảnh chụp của chủ dự án cho thấy rõ. Đây là yêu cầu bắt buộc.
- Canvas có `role="img"` và `aria-label` mô tả nội dung, cộng văn bản dự phòng bên trong
  thẻ.
- Không dùng màu làm dấu hiệu duy nhất; nếu có hai chuỗi thì kèm dấu hiệu thứ hai.

### Trạng thái rỗng

| Tình huống | Hiển thị |
|---|---|
| Phạm vi không có giai đoạn nào | Không hiện bộ chọn và không hiện khung biểu đồ, chỉ một dòng hướng dẫn |
| Giai đoạn được chọn chưa có khu vực nào | Giữ bộ chọn, thay khung biểu đồ bằng "Giai đoạn này chưa có khu vực nào" |

Không hiện khung trắng, không hiện biểu đồ trống trục.

### Phân quyền

Không thêm permission code nào. Route `chart-data` tự kiểm quyền theo dự án
(`progress_read_required`), nên kể cả khi dropdown lọt một cặp ngoài phạm vi thì lệnh
`fetch` vẫn bị chặn. Đó là lớp phòng vệ thứ hai, miễn phí — nhưng **không** được dùng nó
để thay cho việc lọc dropdown cho đúng.

### Kiểm thử bổ sung

- Dropdown chỉ chứa cặp trong phạm vi: test với hai dự án và một người chỉ có
  `can_view_progress` ở một dự án; khẳng định tên dự án kia **không** có trong HTML của
  dropdown.
- `?type_id=` của dự án ngoài phạm vi → xử lý đúng cách đã chọn, và **không** lộ tên
  giai đoạn hay tên dự án trong phản hồi.
- Mặc định chọn đúng giai đoạn ở dòng đầu bảng.
- Hai trạng thái rỗng ở bảng trên.
- HTML có `data-*` chứa URL `chart-data` đúng của cặp đang chọn.
- `tests_js`: đọc `data-*`, gọi `fetch` đã mock, vẽ đúng số cột theo `labels`; và trường
  hợp `labels` rỗng thì không tạo `Chart`.
- Khẳng định div bọc canvas có chiều cao xác định và `maintainAspectRatio: false` trong
  cấu hình.

### Kế hoạch cập nhật

Chèn thành **Bước 4**, dồn bước chốt thành **Bước 5**:

| Bước | Nội dung |
|---|---|
| 4 | Bộ chọn giai đoạn + biểu đồ cột theo khu vực trên dashboard tiến độ |
| 5 | Chốt: thêm mục mới vào cuối `PHASE12_RESULT.md`, gồm cả commit `4bde515` |

Cổng dừng thêm: sau **Bước 4** để chủ dự án bấm thử bộ chọn và biểu đồ.

File được phép sửa, bổ sung so với mục 4:

```
app/static/js/progress-dashboard-chart.js     (hoặc thêm vào file chart dashboard sẵn có)
tests_js/progress-dashboard-chart.test.js
```
