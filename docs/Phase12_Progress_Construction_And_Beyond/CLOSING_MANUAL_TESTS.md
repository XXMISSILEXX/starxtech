# Kiểm thử tay để đóng phase tiến độ thi công

Checklist dùng trước khi coi mô đun tiến độ là xong và giao cho người khác.

Chỉ liệt kê những thứ **tự động hoá không kiểm được**. Phần tự động đã có:

```bash
pytest -p no:cacheprovider -q                       # 620 test, khoảng 6 phút
npm test                                            # 36 test JS
.venv/bin/python scripts/verify_progress_module.py   # bất biến trên dữ liệu thật
```

Chạy cả ba **trước** khi bắt đầu, và chạy lại script bất biến **sau** khi làm xong mục A
và D vì hai mục đó ghi rồi xoá dữ liệu thật.

Dữ liệu dev tại thời điểm viết: dự án `001 · An Bình Homeland`, một giai đoạn
`THI CÔNG PHẦN THÔ`, ba khu vực `C1` / `Tầng hầm` / `Bãi đỗ xe`, sáu hạng mục trong đó
`Điện` đã khai ngày `01/08 → 30/09/2026`, năm hạng mục chưa khai ngày, năm phiếu.

---

## A. Quy mô — khoảng trống lớn nhất

Toàn bộ giao diện chỉ từng được xem với sáu hạng mục. WBS thật của bạn là 80–120 hạng
mục. Không test nào chứng minh giao diện chịu được quy mô đó.

1. Mở overlay **Thêm khu vực**, đặt tên `Kiểm tải`.
2. Bấm **Thêm hạng mục** mười lăm lần. Điền tên, đơn vị, độ chính xác, khối lượng cho
   từng dòng — cứ đặt tên `HM 01` đến `HM 15`.
3. Khai ngày kế hoạch cho khoảng một nửa số dòng.
4. Lưu.

Cần để ý:

- Overlay với mười lăm dòng còn dùng được không, hay phải cuộn quá nhiều để tới nút Lưu.
- Có mất dữ liệu đã nhập khi lỡ có một dòng sai không.
- Tab **Tổng quan** đọc được không với hai mươi mốt hạng mục trên một trang.
- Tab **Biểu đồ Gantt** với khoảng bảy thanh mới: trục còn đọc được không, có cuộn ngang
  trong khung riêng chứ không phải cả trang.
- Dropdown chọn giai đoạn trên dashboard tiến độ vẫn đúng.
- Trang có chậm rõ rệt không.

Nếu overlay hoặc cây hạng mục trở nên khó dùng ở mức này, đó là việc phải sửa **trước**
khi nhập WBS thật, không phải sau.

Giữ khu vực `Kiểm tải` lại để dùng cho mục D, rồi xoá ở cuối.

---

## B. Hai theme

Lỗi nhãn tab vô hình ở Phase 12.3 và biểu đồ đen ở Phase 12.4 đều là lỗi chỉ mắt thấy
được, và đều lọt qua toàn bộ test. Dự án có dark mode nên mọi màn hình phải xem hai lần.

Đổi theme trong **Cài đặt cá nhân**, rồi xem lại:

| Màn hình | Chỗ dễ sai |
|---|---|
| Danh sách loại tiến độ | thanh tiến độ, chữ trên nền thẻ |
| Tab Tổng quan | nhãn "chưa có kế hoạch", nhãn "vượt kế hoạch" |
| Tab Cập nhật ngày | nút Sửa/Xoá, badge trạng thái |
| Tab Biểu đồ Gantt | hai thanh kế hoạch và thực tế có phân biệt được không, vạch đỏ hôm nay |
| Khối tiến độ trên dashboard dự án | badge trạng thái, thanh tiến độ |
| Dashboard tiến độ | **màu cột biểu đồ**, chú giải, dropdown |
| Ba overlay | nhãn, ô đỏ khi lỗi, dòng gợi ý định dạng |

Riêng biểu đồ: cột phải cùng **một** màu (so sánh độ lớn thì một màu), và ô chú giải phải
khớp màu cột — ảnh trước khi sửa có ô chú giải xám mà cột đen.

---

## C. Phân quyền thật, bằng tài khoản thứ hai

Đây là mục quan trọng nhất về mặt an toàn, và là mục duy nhất không thể làm bằng tài
khoản Quản trị tổng — vì tài khoản đó bỏ qua mọi kiểm tra theo dự án.

Tạo hoặc chọn một tài khoản không phải admin, vào **quản lý thành viên dự án 001**, cấp
đúng `Xem tiến độ thi công` và **không** cấp ba capability còn lại. Đăng nhập bằng tài
khoản đó.

Phải thấy:

- Thẻ **Quản lý tiến độ thi công** trong không gian dự án.
- Cả ba tab, đọc được số liệu.
- Khối tiến độ trên dashboard dự án.

Phải **không** thấy:

- Nút `Thêm khu vực`, `Sửa loại`, `Xóa loại`, `Tạo phiếu cập nhật ngày`.
- Nút `Sửa` / `Xóa` trên từng khu vực và trên từng dòng phiếu.

Rồi thử gõ thẳng URL để xác nhận ẩn nút không phải là kiểm soát:

```
POST /projects/1/progress/types            → phải 403
POST /projects/1/progress/types/<id>/delete → phải 403
```

Cách thử nhanh không cần công cụ: mở tab Cập nhật ngày, bấm Back/Forward hoặc dán URL
`?tab=entries` — vẫn đọc được. Còn để thử POST thì cần một tài khoản có quyền tạo phiếu
nhưng không có quyền cấu trúc, rồi bấm nút tạo phiếu: phải thành công, còn mọi thao tác
cấu trúc phải không có nút.

Cuối cùng, **bỏ** capability `Xem tiến độ thi công` của tài khoản đó rồi tải lại:

- Thẻ mô đun **biến mất** khỏi không gian dự án.
- Khối tiến độ **biến mất** khỏi dashboard dự án, nhưng trang vẫn hiện bình thường —
  không phải trang lỗi.
- Vào thẳng `/projects/1/progress` → 403.

---

## D. Đường phá dữ liệu

Xoá cứng đang bật và không hoàn tác được. Phải tự tay xác nhận hộp thoại đếm đúng, vì đó
là thứ duy nhất chặn bạn xoá mất số liệu thật.

1. Trong khu vực `Kiểm tải` ở mục A, chọn một hạng mục và tạo cho nó **hai phiếu** ở hai
   ngày khác nhau.
2. Bấm xoá chính hạng mục đó. Hộp thoại phải nói đúng **2 phiếu**.
3. Gõ **sai tên** trước → phải bị từ chối và **không xoá gì**. Kiểm lại hạng mục vẫn còn.
4. Gõ đúng tên → xoá.
5. Xoá cả khu vực `Kiểm tải`. Hộp thoại phải nói đúng số hạng mục còn lại và số phiếu.

Sau đó chạy lại:

```bash
.venv/bin/python scripts/verify_progress_module.py
```

Phải vẫn "mọi bất biến đúng" — nếu lũy kế lệch sau khi xoá thì đó là lỗi nghiêm trọng.

---

## E. Định dạng số

Đây là loại lỗi đã xảy ra thật hai lần: `937.000` bị đọc thành 937 nghìn, và `1280,34`
bị từ chối. Cả hai đều là lỗi đúng/sai chứ không phải thẩm mỹ.

Trên một hạng mục khai **2 chữ số thập phân**:

| Nhập | Sau khi lưu phải hiện |
|---|---|
| `1280,34` | `1.280,34` |
| `1280.34` | `1.280,34` |
| `1.280,34` | `1.280,34` |
| `1,280.34` | `1.280,34` |

Trên một hạng mục khai **số nguyên**:

| Nhập | Kết quả |
|---|---|
| `1.000` | `1.000` (một nghìn) |
| `1,000` | `1.000` (một nghìn) |
| `12,5` | **bị chặn**, thông báo tiếng Việt nêu rõ chỉ cho 0 chữ số thập phân |

Và kiểm phần trăm hiện `36,8%` với dấu phẩy, không phải `36.8%`.

---

## F. Đối chiếu số giữa các màn hình

Cùng một sự thật hiện ở bốn chỗ. Lệch nhau nghĩa là một chỗ đang tính sai.

1. Phần trăm giai đoạn ở tab **Tổng quan** = phần trăm ở **khối dashboard dự án** = phần
   trăm ở dòng của **dashboard tiến độ**.
2. Phần trăm từng khu vực ở tab Tổng quan = chiều cao cột tương ứng trên **biểu đồ
   dashboard tiến độ**.
3. Dòng "Hoàn thành toàn giai đoạn" dưới biểu đồ = phần trăm giai đoạn ở bảng bên dưới.
4. Số "Chưa khai ngày" trên dashboard = số hạng mục trong dòng cảnh báo ở tab Gantt =
   số script báo ở mục 8 của nó (hiện là **5**).
5. "Cập nhật gần nhất" trên dashboard = ngày phiếu mới nhất ở tab Cập nhật ngày.

---

## G. Ngày và biểu đồ Gantt

1. Vạch đỏ **hôm nay** đúng vị trí trên trục.
2. Hạng mục có `planned_end` đã qua mà chưa đạt 100% phải có nhãn **quá hạn**. Thử bằng
   cách sửa ngày kết thúc của một hạng mục về quá khứ, xem nhãn xuất hiện, rồi sửa lại.
3. Hạng mục đã đạt 100% mà quá ngày kết thúc phải là **Hoàn thành**, **không** phải quá
   hạn. `Điện` đang ở 105,8% nên dùng nó để thử: sửa ngày kết thúc về quá khứ, trạng thái
   phải là Hoàn thành.
4. Hạng mục có "đã làm trước đó" lớn hơn 0 mà chưa khai ngày bắt đầu thực tế phải có dấu
   nhắc rằng thanh thực tế có thể ngắn hơn thực tế.
5. Thanh thực tế **không** chạm vạch hôm nay nếu phiếu cuối cách đây vài ngày.

---

## Hai cửa khác nhau — đừng gộp

### Cửa 1: đóng phase

Đóng được khi đủ ba điều này, và **chỉ ba điều này**:

- Ba lệnh tự động ở đầu tài liệu đều xanh.
- Bảy mục A đến G ở trên đã làm và không còn lỗi chặn.
- Đã chạy lại script bất biến sau mục A và D.

Không có điều kiện nào khác. Phase là phạm vi công việc của mô đun, không phải phạm vi
vận hành của cả hệ thống.

### Cửa 2: cấp quyền xoá cứng cho người thứ hai

Đây là quyết định **sau khi** đóng phase, và nó cần thêm hai điều kiện ghi ở mục 11 của
`PHASE12_1_UX_AND_HARD_DELETE.md`:

- **Đã thử restore backup ít nhất một lần** trên server thật.
- **Có trang xem audit log** trong phần quản trị.

Lý do: xoá cứng không hoàn tác được, và hiện chưa ai ngoài người truy cập được SQL đọc
được audit log để biết ai đã xoá gì. Khi chỉ chủ dự án dùng mô đun thì rủi ro đó nằm
trong tầm kiểm soát — người xoá biết mình vừa xoá gì. Khi có người thứ hai thì không còn
như vậy.

Nên chưa đủ hai điều kiện này **không chặn việc đóng phase**, chỉ chặn việc cấp
`can_manage_progress_structure` cho tài khoản khác.
