# Phase 12.2 — Lỗi trong overlay, danh sách phiếu, và tab

Vòng sửa tiếp sau Phase 12.1. Đọc `CLAUDE.md` trước.
Đặc tả gốc: `PHASE12_CONSTRUCTION_PROGRESS.md`. Vòng trước: `PHASE12_1_UX_AND_HARD_DELETE.md`.

Trạng thái: **chưa triển khai**. Nguồn yêu cầu: chủ dự án sau khi test tay 12.1.

---

## 0. Quyết định đã chốt

**Biểu đồ Gantt: HOÃN.** Lý do kỹ thuật, không phải ưu tiên: `ProgressItem` hiện
**không có cột ngày nào**; trường ngày duy nhất trong mô đun là
`ProgressEntry.report_date`. Gantt vẽ công việc trên trục thời gian nên cần ngày
bắt đầu và kết thúc — dữ liệu đó chưa tồn tại.

Khi làm Gantt sau này, hai hướng đã cân nhắc:

1. Thêm `planned_start_date` và `planned_end_date` vào `ProgressItem`, khai trong
   overlay, vẽ thanh kế hoạch làm nền và thanh thực tế (từ phiếu đầu tới phiếu
   cuối) đè lên. Đây là Gantt đúng nghĩa cho xây dựng: thấy được chậm hay đúng hạn.
2. Chỉ suy từ phiếu đã có: thanh chạy từ phiếu đầu tới phiếu gần nhất. Không cần
   khai gì nhưng không có kế hoạch để so, và hạng mục chưa có phiếu sẽ không có
   thanh nào.

**Không thêm tab Gantt rỗng** trong vòng này. Một tab trống là nợ kỹ thuật và làm
người dùng tưởng tính năng bị lỗi.

Quyết định kỹ thuật cho vòng này:

3. **Lỗi trong overlay xử lý phía server**, không dùng AJAX. Khi validate thất bại,
   trang render lại kèm dấu hiệu mở đúng overlay đó và bản đồ lỗi theo từng dòng.
   Lý do: giữ kiến trúc không-SPA của repo, test được hoàn toàn ở tầng server, và
   là delta nhỏ so với hiện tại (dữ liệu đã nhập đã được giữ lại từ 12.1).
4. **Tab là đường dẫn thật** (`?tab=...`), không phải tab chỉ chạy bằng JavaScript.
   Danh sách phiếu cần phân trang và bộ lọc, nên mỗi tab phải có URL riêng để lưu
   được, chia sẻ được, và bấm Back hoạt động đúng.
5. **Bỏ hẳn route tạo phiếu đơn lẻ** `create_entry`. Sau mục 4, không giao diện nào
   gọi nó, và một route không có giao diện là bề mặt chết. Overlay phiếu hàng loạt
   với một dòng làm được đúng việc đó.

---

## 1. Lỗi hiển thị ngay trong overlay (yêu cầu 1)

### Hiện tại sai ở đâu

Khi batch bị từ chối, server render lại trang, **giữ được dữ liệu đã nhập** nhưng
overlay đã đóng, và lỗi hiện thành một dải băng vàng ở đầu trang:

> Dòng 2: hạng mục 'Điện' bị trùng trong lượt tạo phiếu.

Người dùng phải tự mở lại overlay, và khi mở ra thì không biết dòng nào sai.

### Phải thành

- Overlay **tự mở lại** đúng cái vừa submit, ngay khi trang tải xong.
- Lỗi hiện **cạnh đúng ô hoặc đúng dòng gây lỗi**, dùng `is-invalid` và
  `invalid-feedback` của Bootstrap. Dòng có lỗi được đánh dấu rõ.
- Dữ liệu người dùng đã nhập giữ nguyên, kể cả các dòng hợp lệ.
- Dải băng ở đầu trang chỉ còn là câu tổng kết ngắn, hoặc bỏ hẳn. Lỗi thuộc về ô
  nhập, không thuộc về đầu trang.

Áp dụng cho cả ba overlay: tạo khu vực, sửa khu vực, tạo phiếu cập nhật ngày.

### Cách làm

Service trả về lỗi có cấu trúc thay vì một chuỗi: khoá theo chỉ số dòng và tên
trường, ví dụ `{"rows": {1: {"item_id": "Hạng mục bị trùng trong lượt tạo phiếu."}}}`,
cộng một danh sách lỗi cấp form. Route đưa cấu trúc đó cùng `open_modal` vào
template. Một đoạn JS ngắn đọc `open_modal` và mở modal tương ứng.

Không đổi quy tắc nghiệp vụ: batch vẫn là tất-cả-hoặc-không, vẫn không lưu gì khi
có một dòng sai.

---

## 2. Danh sách phiếu cập nhật ngày (yêu cầu 2)

Bảng ở phạm vi một loại tiến độ, là một tab của trang chi tiết loại.

Cột: ngày, khu vực, hạng mục, khối lượng (dùng `vn_number` theo `decimal_places`
của hạng mục), đơn vị, ghi chú, người tạo, hành động.

- Sắp xếp ngày mới nhất trước.
- **Phân trang bắt buộc.** Một dự án chạy một năm có thể có hàng nghìn phiếu; trang
  không giới hạn là vấn đề hiệu năng và cũng là thứ `CLAUDE.md` yêu cầu chú ý.
- Bộ lọc: khoảng ngày, và khu vực. Không cần nhiều hơn ở vòng này.
- **Sửa phiếu**: mở overlay gồm ngày, khối lượng, ghi chú. Dùng lại route
  `change_entry` với `action=edit`. Vẫn chịu quy tắc một phiếu một ngày, chặn ngày
  tương lai, và kiểm số chữ số thập phân.
- **Xoá phiếu**: hộp thoại xác nhận nêu rõ ngày, hạng mục và khối lượng sắp mất.
  **Không** bắt gõ tên — một phiếu là một hàng, gõ tên là quá nặng. Vẫn ghi audit.
- Quyền: xem cần `can_view_progress`. Sửa và xoá giữ nguyên quy tắc hiện tại —
  người tạo phiếu, hoặc người có `can_edit_all_progress_entries`. Không nới thêm.

Nút sửa và xoá **không được render** cho người không có quyền, và route tương ứng
vẫn phải trả 403 — ẩn trên giao diện không phải kiểm soát.

---

## 3. Sửa lệch dòng và đổi nhãn (yêu cầu 3)

### Nguyên nhân lệch dòng

`type_detail.html` macro `item_row` dùng `<div class="row g-2 align-items-end">`.
Hai cột "Kế hoạch" và "Mang sang" có thêm một khối gợi ý `Ví dụ: 1.280` bên dưới ô
nhập nên cao hơn các cột khác. Với `align-items-end`, mọi cột căn theo đáy, nên cột
cao hơn bị đẩy nhãn lên trên — đúng hiện tượng trong ảnh chủ dự án gửi.

### Sửa

Đưa ví dụ vào `placeholder` của ô nhập và bỏ khối gợi ý riêng. Khi đó mọi cột có
cùng cấu trúc và cùng chiều cao. Đổi `align-items-end` sang `align-items-start` cho
chắc. Áp dụng cho cả `item_row` và `entry_row`.

### Đổi nhãn

"Mang sang" → **"Đã làm trước đó"** ở mọi nơi: nhãn trong overlay, thẻ số ở trang
hạng mục, dòng cuối bảng lịch sử, và các assertion trong test đang dùng chuỗi cũ.

---

## 4. Trang hạng mục chỉ còn thông tin và lịch sử (yêu cầu 4)

Bấm vào một hạng mục như "Điện" hiện ra trang tạo phiếu. Phải bỏ.

Trang hạng mục còn lại:

- Bốn thẻ số: kế hoạch, đã làm, còn lại, phần trăm hoàn thành.
- Bảng **lịch sử cập nhật của hạng mục đó qua các ngày**: ngày, khối lượng, ghi
  chú, người tạo, và hành động sửa/xoá theo đúng quyền như mục 2.
- Dòng cuối "Đã làm trước đó" kèm chú thích, giữ như hiện tại.
- **Bỏ form tạo phiếu** và **bỏ route `create_entry`** cùng các test chỉ phục vụ
  nó. Cập nhật ma trận phân quyền trong `tests/test_construction_progress_authz.py`
  cho khớp.

Layout trang này hiện chưa được trau (nhãn nằm ngang với ô nhập, không có thẻ card).
Dựng lại theo cùng cấu trúc card và bảng như phần còn lại của mô đun.

---

## 5. Tab trong trang chi tiết loại (yêu cầu 6)

Hai tab, là đường dẫn thật:

| Tab | URL | Nội dung |
|---|---|---|
| Tổng quan | `.../types/<id>` | Cây khu vực và hạng mục như hiện tại |
| Cập nhật ngày | `.../types/<id>?tab=entries` | Danh sách phiếu ở mục 2 |

Nút "Tạo phiếu cập nhật ngày", "Thêm khu vực", "Sửa loại", "Xóa loại" giữ nguyên ở
đầu trang, hiện trên cả hai tab.

Giá trị `tab` không hợp lệ trả 400 hoặc mặc định về Tổng quan — chọn một và test nó.
Không được dùng giá trị `tab` để dựng tên template hay tên thuộc tính.

---

## 6. Kế hoạch thi hành

Sáu bước, mỗi bước một commit, mỗi commit `pytest` xanh toàn bộ.
**Ngân sách pytest ít nhất 20 phút** — suite khoảng 6 phút.

| Bước | Nội dung | Lý do xếp ở đây |
|---|---|---|
| 0 | Mốc xanh, ghi `BASELINE_12_2.md` | Không có mốc thì test đỏ sau này không quy được trách nhiệm |
| 1 | Mục 3: lệch dòng, `placeholder`, đổi nhãn "Đã làm trước đó" | Nhỏ, độc lập, không phụ thuộc gì |
| 2 | Mục 1: lỗi có cấu trúc, tự mở lại overlay, đánh dấu dòng sai | Ảnh hưởng cả ba overlay, làm trước khi thêm overlay mới |
| 3 | Mục 4: trang hạng mục, bỏ form và route `create_entry` | Giảm số đường ghi trước khi thêm màn hình mới |
| 4 | Mục 2 + 5: danh sách phiếu, phân trang, bộ lọc, sửa/xoá phiếu, hai tab | Hai mục này gắn nhau, tách ra sẽ phải sửa template hai lần |
| 5 | Chốt: cập nhật mục 10 của `PHASE12_RESULT.md` | |

Cổng dừng: sau **Bước 2** để chủ dự án bấm thử phần lỗi trong overlay, và sau
**Bước 4** trước khi chốt.

### File được phép sửa

```
app/construction_progress/routes.py
app/construction_progress/services.py
app/templates/construction_progress/*.html
app/static/js/construction-progress-overlays.js
tests/test_construction_progress_*.py
tests_js/construction-progress-overlays.test.js
docs/Phase12_Progress_Construction_And_Beyond/BASELINE_12_2.md
docs/Phase12_Progress_Construction_And_Beyond/PHASE12_RESULT.md  (chỉ thêm vào mục 10)
```

Cấm chạm: `app/models/progress.py` (vòng này **không** đổi schema, không migration),
`app/config.py`, `pytest.ini`, `app/auth/permissions.py`, `app/permissions/registry.py`,
`app/project_memberships.py`, `.audit/**`, và bốn primitive
`project_read_required`/`project_write_required`/`project_manage_required`/`can_write_project`.

Không có migration trong vòng này. Nếu một bước có vẻ cần đổi schema thì **DỪNG và
báo** — nghĩa là hiểu sai phạm vi.

### Kiểm thử bắt buộc

- Mỗi overlay: submit sai → response chứa dấu hiệu mở lại đúng modal đó, chứa lỗi
  gắn với đúng chỉ số dòng, và giữ nguyên dữ liệu đã nhập ở mọi dòng.
- Batch vẫn tất-cả-hoặc-không: assert **không hàng nào** được tạo, sửa, hay xoá, và
  `AuditLog` không có bản ghi mới. Đây là assertion phủ định, dễ viết sai mà vẫn pass.
- Danh sách phiếu: phân trang đúng, từng bộ lọc đúng, sắp xếp ngày mới nhất trước.
- Danh sách phiếu: người thiếu quyền sửa **không** thấy nút, **và** route trả 403.
- Sửa phiếu qua overlay: trùng ngày bị chặn, ngày tương lai bị chặn, vượt
  `decimal_places` bị chặn — không hàng nào đổi.
- Xoá phiếu: audit có `old_values` chứa ngày, khối lượng, ghi chú, người tạo.
- Trang hạng mục: không còn form tạo phiếu; `POST` tới route `create_entry` cũ trả
  404 sau khi bỏ.
- Tab: giá trị `tab` không hợp lệ xử lý đúng như đã chọn; cả hai tab render đúng nội
  dung; ma trận 8 vai vẫn xanh cho cả hai URL.
- Nhãn: không còn chuỗi "Mang sang" ở bất kỳ template nào.
- `grep -rnF '\x' tests/test_construction_progress_*.py` phải rỗng. Assertion tiếng
  Việt dùng `response.get_data(as_text=True)`, không dùng byte literal.
- `npm test`: dán nguyên văn khối tổng kết của `node --test`, không đếm số file.

### Ngoài phạm vi

Biểu đồ Gantt và mọi cột ngày mới (xem mục 0). Dashboard và biểu đồ — route
`chart-data` vẫn giữ nguyên cho phase đó. Import Excel, ảnh đính kèm cho phiếu,
duyệt phiếu, và test đồng thời PostgreSQL cho mô đun tiến độ (đang có task riêng).
