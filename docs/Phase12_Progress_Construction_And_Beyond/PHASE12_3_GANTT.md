# Phase 12.3 — Biểu đồ Gantt theo khu vực

Vòng sửa tiếp sau Phase 12.2. Đọc `CLAUDE.md` trước.
Đặc tả gốc: `PHASE12_CONSTRUCTION_PROGRESS.md`. Hai vòng trước:
`PHASE12_1_UX_AND_HARD_DELETE.md`, `PHASE12_2_ENTRY_LIST_AND_OVERLAY_ERRORS.md`.

Trạng thái: **chưa triển khai**. Nguồn yêu cầu: chủ dự án sau khi dùng thử 12.2.

---

## 0. Yêu cầu và quyết định

### Chủ dự án yêu cầu

1. Mỗi **hạng mục** có thể khai ngày bắt đầu và ngày kết thúc kế hoạch, hoặc không khai.
2. Ngày của **khu vực** là ngày bắt đầu sớm nhất và ngày kết thúc muộn nhất của các
   hạng mục bên trong — **giá trị dẫn xuất, không nhập tay**.
3. Ngày khai trong overlay tạo và sửa khu vực.
4. Hạng mục **chỉ xuất hiện trên Gantt khi đã khai đủ ngày kế hoạch**. Chưa khai thì
   không có trên biểu đồ. Biểu đồ tự sinh theo những gì đã khai.
5. Vẽ **cả hai thanh**: kế hoạch và thực tế.
6. Có thêm **ngày bắt đầu thực tế** cho người dùng tự điền. **Không** có ngày kết thúc
   thực tế.

### Vì sao bắt đầu thực tế nhập tay mà kết thúc thực tế thì không

Đây là nguyên tắc phân định, không phải sở thích:

**Ngày bắt đầu thực tế nhập tay** vì nó thỏa hai điều kiện. Hệ thống **không thể biết**
nó — với hạng mục đã thi công trước khi dùng hệ thống, `opening_quantity` cho biết khối
lượng nhưng không có mốc thời gian nào. Và nó **ghi một lần là xong** — ngày một công
việc bắt đầu không thay đổi về sau, nên trường này không bao giờ lỗi thời.

**Ngày kết thúc thực tế suy từ phiếu** vì cả hai điều kiện đều không thỏa. Hệ thống đã
biết nó: chính là ngày phiếu muộn nhất. Và nếu nhập tay thì nó **sẽ lỗi thời** — người
dùng điền một lần lúc khai kế hoạch rồi không ai quay lại sửa khi công việc thực sự
xong. Một ngày kết thúc cũ trên Gantt tệ hơn không có ngày nào, vì nó khẳng định một
điều sai. Phiếu thì được nhập hằng ngày như một phần công việc, nên ngày suy từ phiếu
luôn đúng mà không ai phải nhớ gì.

Ngoài ra, nhập tay ngày kết thúc sẽ tạo hai nguồn cho cùng một sự thật và chúng sẽ lệch
nhau — trái nguyên tắc mô đun đã chốt từ Phase 12: chỉ hạng mục nhỏ mang dữ liệu gốc,
mọi thứ suy ra được thì không lưu.

### Quyết định kỹ thuật

7. **Không lưu ngày ở cấp khu vực.** Suy khi đọc, giống cách phần trăm đang làm.
8. **Ngày kế hoạch là cả-hai-hoặc-không.** Khai một trong hai bị chặn kèm thông báo
   tiếng Việt. Cho khai lẻ sẽ tạo ra hàng nửa vời không bao giờ lên biểu đồ mà không ai
   hiểu vì sao.
9. **Không thêm thư viện biểu đồ.** Vẽ bằng HTML và CSS render từ server, theo đúng quy
   tắc không-SPA của repo. Gantt là các thanh định vị theo phần trăm chiều rộng.
10. **Tab thứ ba** `?tab=gantt`, cùng cơ chế đường dẫn thật như 12.2.

---

## 1. Thay đổi dữ liệu

Thêm vào `progress_items`, cả ba đều `nullable=True`:

| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| `planned_start_date` | Date | Ngày bắt đầu theo kế hoạch |
| `planned_end_date` | Date | Ngày kết thúc theo kế hoạch |
| `actual_start_date` | Date | Ngày bắt đầu thực tế, do người dùng khai |

CheckConstraint:

- `ck_progress_items_planned_dates_paired`:
  `(planned_start_date IS NULL) = (planned_end_date IS NULL)`
- `ck_progress_items_planned_date_order`:
  `planned_start_date IS NULL OR planned_start_date <= planned_end_date`

`actual_start_date` không có CheckConstraint vì ràng buộc của nó là "không sau hôm nay",
mà database không biết hôm nay là ngày nào. Kiểm ở tầng service bằng `local_today()`.

Không thêm cột nào vào `progress_groups` — ngày của khu vực là dẫn xuất (quyết định 7).

Một migration duy nhất. `downgrade()` bỏ cả ba cột và hai constraint.

---

## 2. Quy tắc suy diễn

### Cấp hạng mục

```
thanh kế hoạch = [planned_start_date, planned_end_date]      (bắt buộc để lên biểu đồ)

bắt đầu thực tế  = actual_start_date nếu có
                   ngược lại là ngày phiếu sớm nhất
                   nếu không có cả hai thì KHÔNG có thanh thực tế
kết thúc thực tế = ngày phiếu muộn nhất nếu có
                   ngược lại là chính ngày bắt đầu thực tế
```

Bốn trường hợp cần xử lý đúng:

- **Có `actual_start_date`, chưa có phiếu nào**: thanh thực tế là một điểm tại
  `actual_start_date`. Vẽ thành dấu nhỏ nhìn thấy được, không phải thanh rộng 0 pixel.
  Nghĩa của nó là "đã bắt đầu, chưa có phiếu nào" — **không** kéo thanh tới hôm nay,
  vì kéo tới hôm nay là khẳng định công việc đang chạy mà dữ liệu không nói vậy.
- **`actual_start_date` muộn hơn ngày phiếu sớm nhất**: lấy `min` của hai giá trị. Một
  phiếu là bằng chứng cứng rằng ngày đó đã có việc, nên bằng chứng sớm hơn thắng. Không
  chặn lưu — người dùng khai sai một ngày không nên bị chặn bởi một phiếu ở màn hình khác.
- **Không `actual_start_date`, không phiếu**: không có thanh thực tế. Không có gì để suy.
- **`opening_quantity > 0` mà `actual_start_date` trống**: vẫn lưu bình thường, nhưng
  biểu đồ hiện dòng nhắc rằng thanh thực tế của hạng mục đó có thể ngắn hơn thực tế, vì
  phần khối lượng làm trước khi dùng hệ thống không có phiếu nào. Nhắc, không chặn.

Thanh thực tế **không kéo tới hôm nay** khi đã có phiếu. Nếu hạng mục còn 45% mà phiếu
cuối cách đây ba tuần, thanh dừng ở ba tuần trước — khoảng trống tới vạch hôm nay chính
là thông tin: công việc đang dừng. Kéo tới hôm nay sẽ che mất điều đó.

### Cấp khu vực

```
kế hoạch = [min(planned_start_date), max(planned_end_date)]  trên các hạng mục đã khai ngày
thực tế  = [min(bắt đầu thực tế),    max(kết thúc thực tế)]   trên cùng tập hạng mục đó
```

Khu vực không có hạng mục nào khai ngày kế hoạch thì **không xuất hiện** trên biểu đồ.

### Hạng mục bị loại — phải hiện, không được ẩn im lặng

Hạng mục chưa khai ngày kế hoạch bị loại khỏi biểu đồ theo yêu cầu 4. Nhưng biểu đồ
**phải hiện số lượng bị loại** ở đầu tab, ví dụ:

> 3 hạng mục chưa khai ngày kế hoạch nên không có trên biểu đồ.

Kèm danh sách tên khi bấm vào. Lý do: một hạng mục vô hình và bị quên là cách nhanh nhất
để biểu đồ nói sai về tiến độ dự án. Người dùng phải biết mình đang không thấy gì.

---

## 3. Nhập ngày trong overlay

Thêm vào mỗi hàng hạng mục của overlay tạo và sửa khu vực: ba ô ngày —
"Bắt đầu (kế hoạch)", "Kết thúc (kế hoạch)", "Bắt đầu thực tế".

**Bố cục là việc thật, không phải chi tiết nhỏ.** Hàng hạng mục hiện có sáu ô (tên, đơn
vị, độ chính xác, kế hoạch, đã làm trước đó, xoá); thêm ba ô nữa là chín. Một hàng chín
ô sẽ tràn ngang trên màn hình hẹp. Chia hàng thành hai dòng con: dòng khối lượng (tên,
đơn vị, độ chính xác, kế hoạch, đã làm trước đó) và dòng thời gian (ba ngày), với nút
xoá đặt ở vị trí rõ ràng cho cả hàng.

Kiểm ở server:

| Điều kiện | Xử lý |
|---|---|
| Khai một trong hai ngày kế hoạch | Chặn theo dòng: "Cần khai cả ngày bắt đầu và ngày kết thúc kế hoạch, hoặc để trống cả hai." |
| `planned_start_date > planned_end_date` | Chặn theo dòng |
| `actual_start_date` sau hôm nay | Chặn theo dòng, so với `local_today()` |
| Ngày không đọc được | Chặn theo dòng, dùng `parse_iso_date`, không tự parse |

Được phép và **không** được coi là lỗi:

- Ngày kế hoạch ở quá khứ hoặc tương lai.
- `actual_start_date` sớm hơn `planned_start_date` — bắt đầu sớm hơn kế hoạch là chuyện
  thật, và đó chính là thông tin cần thấy.
- `actual_start_date` có mà chưa khai ngày kế hoạch — lưu được, chỉ là hạng mục đó chưa
  lên biểu đồ.

Lỗi hiện trong overlay theo đúng cơ chế `data-open-progress-modal` của 12.2, giữ nguyên
dữ liệu đã nhập, và batch vẫn là tất-cả-hoặc-không.

---

## 4. Vẽ biểu đồ

Tab thứ ba `?tab=gantt`. Nhóm nút hành động ở đầu trang giữ nguyên trên cả ba tab.

### Trục thời gian

Khoảng hiển thị = từ ngày sớm nhất tới ngày muộn nhất trong **tất cả** thanh sẽ vẽ (cả
kế hoạch và thực tế), mở rộng để luôn chứa hôm nay nếu hôm nay nằm ngoài. Sau đó làm
tròn ra ngoài theo mốc chia.

Mốc chia chọn theo độ dài khoảng:

| Khoảng | Mốc |
|---|---|
| ≤ 31 ngày | theo ngày |
| ≤ 26 tuần | theo tuần |
| dài hơn | theo tháng |

Nhãn mốc theo định dạng Việt, dùng bộ lọc ngày sẵn có của repo.

### Thân biểu đồ

- Mỗi khu vực là một nhóm: một dòng tổng của khu vực, rồi các dòng hạng mục bên trong.
- Mỗi dòng có hai thanh xếp trên dưới: **kế hoạch** và **thực tế**. Hai thanh phải phân
  biệt được bằng cả màu **và** một dấu hiệu thứ hai (viền, gạch chéo, hoặc độ dày) —
  không được chỉ dựa vào màu.
- **Vạch dọc "hôm nay"** xuyên toàn biểu đồ. Đây là chi tiết hữu ích nhất trên một
  Gantt: nó cho biết cái gì đã quá hạn.
- Mỗi dòng hạng mục hiện phần trăm hoàn thành ở cuối, dùng `vn_number(places=1)`.
  **Không** dùng phần trăm để tô đầy thanh thời gian — trộn tiến độ khối lượng vào trục
  thời gian sẽ khiến người đọc hiểu sai.
- Hạng mục quá hạn (`planned_end_date` đã qua mà phần trăm chưa đạt 100) được đánh dấu
  rõ, ví dụ nhãn "quá hạn".
- Hạng mục có `opening_quantity > 0` mà chưa khai `actual_start_date`: hiện dấu nhắc
  rằng thanh thực tế có thể ngắn hơn thực tế, kèm giải thích ngắn khi đưa chuột vào.
- Thanh thực tế là một điểm (đã bắt đầu, chưa có phiếu) phải vẽ thành dấu nhìn thấy được
  kèm nhãn giải thích.
- Thứ tự: khu vực theo ngày bắt đầu kế hoạch sớm nhất; hạng mục trong khu vực theo ngày
  bắt đầu kế hoạch, rồi theo tên.

### Kỹ thuật và tiếp cận

- Thuần HTML/CSS render từ server. Vị trí và chiều rộng tính bằng phần trăm so với khoảng
  trục. Không thêm thư viện, không canvas.
- Mỗi thanh có `aria-label` nêu tên hạng mục và hai mốc ngày, vì thanh CSS không đọc được
  bằng trình đọc màn hình.
- Biểu đồ phải cuộn ngang được trong khung riêng khi trục dài; **trang không được cuộn
  ngang**.
- Trạng thái rỗng: chưa hạng mục nào khai ngày thì hiện hướng dẫn khai ở đâu, không hiện
  một khung trắng.

---

## 5. Kế hoạch thi hành

Sáu bước, mỗi bước một commit, mỗi commit `pytest` xanh toàn bộ.
**Ngân sách pytest ít nhất 20 phút.**

| Bước | Nội dung | Lý do xếp ở đây |
|---|---|---|
| 0 | Mốc xanh, ghi `BASELINE_12_3.md` | Không có mốc thì test đỏ sau này không quy được trách nhiệm |
| 1 | Ba cột ngày + hai CheckConstraint + migration | Nền của mọi bước sau |
| 2 | Ba ô ngày trong overlay + validate + chia hàng thành hai dòng con | Không có dữ liệu thì không vẽ được gì |
| 3 | Hàm suy diễn: khoảng kế hoạch, khoảng thực tế, đếm hạng mục bị loại | Hàm thuần, test độc lập được |
| 4 | Tab `?tab=gantt`: trục, mốc chia, hai thanh, vạch hôm nay, nhãn quá hạn, dấu nhắc | Phần vẽ, sau khi số đã đúng |
| 5 | Chốt: thêm mục mới vào `PHASE12_RESULT.md` | |

Cổng dừng: sau **Bước 2** để chủ dự án khai ngày thử trên dữ liệu thật và xem bố cục
overlay chín ô có dùng được không, và sau **Bước 4** để bấm thử biểu đồ.

### File được phép sửa

```
app/models/progress.py                     ba cột ngày + constraint
app/models/__init__.py
app/construction_progress/services.py      suy diễn khoảng thời gian
app/construction_progress/routes.py        tab gantt
app/templates/construction_progress/*.html overlay + biểu đồ
app/static/js/construction-progress-overlays.js  nếu cần
migrations/versions/<hash>_*.py            một migration
tests/test_construction_progress_*.py
tests_js/construction-progress-overlays.test.js
docs/.../BASELINE_12_3.md
docs/.../PHASE12_RESULT.md                 chỉ thêm mục mới ở cuối
```

Cấm chạm: `app/config.py`, `pytest.ini`, `app/auth/permissions.py`,
`app/permissions/registry.py`, `app/project_memberships.py`, `.audit/**`, và bốn primitive
`project_read_required`/`project_write_required`/`project_manage_required`/`can_write_project`.
Vòng này **không thêm quyền mới** — xem Gantt dùng `can_view_progress`, khai ngày dùng
`can_manage_progress_structure`, giống sửa hạng mục.

### Kiểm thử bắt buộc

Hàm suy diễn, test như hàm thuần:

- Khai đủ hai ngày kế hoạch → có thanh kế hoạch.
- Khai lẻ một ngày → bị chặn ở tầng service **và** CheckConstraint chặn ở tầng database.
- `planned_start > planned_end` → chặn ở cả hai tầng.
- Không `actual_start_date`, có 3 phiếu → thanh thực tế từ phiếu sớm nhất tới phiếu muộn
  nhất.
- Có `actual_start_date` sớm hơn phiếu đầu → thanh thực tế bắt đầu từ ngày khai.
- Có `actual_start_date` **muộn hơn** phiếu đầu → lấy ngày phiếu, tức `min` của hai giá
  trị, và **không** chặn lưu.
- Có `actual_start_date`, chưa có phiếu → thanh là một điểm, không kéo tới hôm nay,
  không nổ lỗi.
- Không `actual_start_date`, không phiếu → **không có thanh thực tế**.
- Khoảng của khu vực = min bắt đầu và max kết thúc của các hạng mục đã khai ngày, bỏ qua
  hạng mục chưa khai.
- Khu vực không có hạng mục nào khai ngày → không xuất hiện.
- Đếm hạng mục bị loại đúng số.

Overlay và HTTP:

- Khai lẻ một ngày kế hoạch → 400, overlay tự mở lại, lỗi gắn đúng dòng, **không hàng
  nào được tạo hoặc sửa**.
- `actual_start_date` sau `local_today()` → chặn theo dòng.
- `actual_start_date` sớm hơn `planned_start_date` → lưu **thành công**, không phải lỗi.
- `actual_start_date` có mà chưa khai ngày kế hoạch → lưu thành công.
- Ngày rác không đọc được → chặn theo dòng, không nổ trang.
- Assertion thứ tự HTML `data-open-progress-modal` trước
  `construction-progress-overlays.js` vẫn phải đúng, như 12.2.

Tab và biểu đồ:

- `?tab=gantt` render đúng; ma trận 8 vai xanh cho **cả ba** URL tab.
- `tab` không hợp lệ xử lý như 12.2 đã chọn.
- Trạng thái rỗng khi chưa hạng mục nào khai ngày.
- Số hạng mục bị loại hiện đúng trên trang.
- Vạch hôm nay có mặt.
- Nhãn "quá hạn" xuất hiện đúng khi `planned_end_date` đã qua và phần trăm chưa đạt 100,
  và **không** xuất hiện khi đã đạt 100.
- Dấu nhắc xuất hiện đúng khi `opening_quantity > 0` và `actual_start_date` trống, và
  **không** xuất hiện khi đã khai `actual_start_date`.
- Mốc chia đổi đúng theo ba ngưỡng 31 ngày / 26 tuần / dài hơn.

Chốt: `grep -rnF '\x' tests/test_construction_progress_*.py` phải rỗng. Assertion tiếng
Việt dùng `get_data(as_text=True)`. JS: dán cả
`grep -h '^test(' tests_js/*.test.js | wc -l` và khối tổng kết node.

### Ngoài phạm vi

**Ngày kết thúc thực tế** — suy từ phiếu, xem mục 0. Kéo thả để đổi ngày trên biểu đồ.
Quan hệ phụ thuộc giữa các hạng mục (đường nối, đường găng). Xuất biểu đồ ra ảnh hoặc
PDF. Gantt ở cấp toàn dự án hay nhiều loại tiến độ cùng lúc. Dashboard và `chart-data` —
vẫn để phase riêng.
