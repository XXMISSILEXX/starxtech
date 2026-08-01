# Phase 12.1 — Overlay, định dạng số, và xoá cứng

Vòng sửa tiếp sau Phase 12 (`PHASE12_RESULT.md`). Đọc `CLAUDE.md` trước.
Đặc tả gốc của mô đun: `PHASE12_CONSTRUCTION_PROGRESS.md` — vẫn còn hiệu lực trừ
những chỗ tài liệu này nói rõ là thay thế.

Trạng thái: **chưa triển khai**.

---

## 0. Lỗi nghiêm trọng nhất, không nằm trong danh sách người dùng nêu

Trang chi tiết đang hiện `151.000 / 937.000 mét` cho một hạng mục có kế hoạch
**937 mét**. Nguyên nhân: cột `Numeric(18,3)` được in thẳng ra template
(`type_detail.html` dùng `{{ item.planned_quantity }}`), nên `Decimal("937.000")`
render đúng như vậy.

Trong tiếng Việt, dấu `.` là **dấu phân cách nghìn**. Mọi người đọc báo cáo sẽ
hiểu đó là **937 nghìn mét** — sai lệch 1000 lần trên một số liệu tiến độ dùng để
báo cáo. Đây là lỗi đúng/sai, không phải lỗi thẩm mỹ, và phải sửa trước mọi việc
khác trong vòng này.

Phần trăm cũng đang hiện `16.1%` thay vì `16,1%`.

---

## 1. Quyết định sản phẩm đã chốt

Chủ dự án đã chốt trong phiên làm việc:

1. **Xoá cứng có xoá theo phiếu bên trong.** Hộp thoại xác nhận phải nêu chính xác
   số lượng sẽ mất, người dùng phải gõ đúng tên để xác nhận, và toàn bộ nội dung
   bị xoá được ghi vào audit log **trước khi** xoá.
2. **Bỏ hẳn chức năng Ẩn.** Chỉ còn xoá. Kéo theo: cột `is_active` trên ba bảng
   cấu trúc bị loại bỏ, và các bản ghi đang ẩn phải được dọn trước.

Đã xác nhận lại sau khi cân nhắc xoá mềm: **khối lượng trong mô đun này không liên
quan tới nghiệm thu hay thanh toán ở phase hiện tại**, nên xoá cứng là hướng chốt.
Xem mục 11 cho điều kiện trước khi bật trên production, và mục 12 cho điều kiện
phải xem lại quyết định này.

Quyết định kỹ thuật đi kèm (không cần hỏi lại):

3. **Độ chính xác thập phân gắn theo hạng mục**, không gắn theo một danh mục đơn
   vị dùng chung. Đơn vị là chuỗi tự do như hiện tại; mỗi hạng mục tự khai số chữ
   số thập phân 0–3.
4. **Phiếu hàng loạt là tất-cả-hoặc-không.** Một transaction; dòng nào sai thì cả
   phiếu không lưu, kèm thông báo chỉ rõ dòng nào sai. Lưu một phần sẽ tạo trạng
   thái nửa vời mà người dùng không biết đã lưu được gì.
5. **Quyền xoá cấu trúc dùng lại `can_manage_progress_structure`**, không thêm
   capability thứ năm. An toàn dựa vào hộp thoại xác nhận có gõ tên và audit đầy
   đủ. Nếu sau này cần "sửa được nhưng không xoá được" thì mới tách flag riêng.

---

## 2. Cái bẫy về thứ tự — đọc trước khi lập lịch

Hiện tại có bản ghi đang `is_active = false`. Nếu xoá cột `is_active` trước khi dọn
chúng, **những thứ đang ẩn sẽ hiện trở lại** vì không còn cột nào để lọc.

Thứ tự bắt buộc:

1. Có xoá cứng hoạt động (Bước 2).
2. Dọn hết bản ghi đang ẩn bằng chính chức năng đó (Bước 3).
3. Chỉ khi đó mới migration xoá cột `is_active`, và migration phải **tự chặn** nếu
   còn bất kỳ hàng nào `is_active = false`.

Migration không được tự ý xoá dữ liệu kinh doanh. Nó chỉ được phép fail và yêu cầu
người vận hành dọn trước.

---

## 3. Định dạng số và đơn vị (mục 5 của người dùng)

### Thay đổi dữ liệu

Thêm vào `progress_items`:

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `decimal_places` | SmallInteger not null default 0 | `CheckConstraint decimal_places BETWEEN 0 AND 3` |

Không đổi `Numeric(18,3)` — nó vẫn là kho chứa. `decimal_places` là **hợp đồng
nhập liệu và hiển thị**, không phải kiểu lưu trữ.

### Nhập liệu

Form tạo/sửa hạng mục có dropdown: "Số nguyên", "1 chữ số thập phân",
"2 chữ số thập phân", "3 chữ số thập phân".

Ví dụ nghiệp vụ: "Căn hộ" và "cái" là số nguyên; "mét" và "m²" thường 1–2 chữ số.

Server phải **từ chối** giá trị có nhiều chữ số thập phân hơn mức khai báo, cho cả
`planned_quantity`, `opening_quantity`, và `quantity` của phiếu. Thông báo tiếng
Việt nêu rõ mức cho phép. Thuộc tính `step` trên input chỉ là tiện lợi, không phải
kiểm soát.

### Hiển thị

Thêm một Jinja filter định dạng số kiểu Việt, đặt cạnh filter ngày hiện có:

```
vn_number(1234.5, places=1)  -> "1.234,5"
vn_number(937,    places=0)  -> "937"
vn_number(937,    places=2)  -> "937,00"
```

Dấu phân cách nghìn là `.`, dấu thập phân là `,`. Áp dụng cho **mọi** số khối
lượng, số tiền, và phần trăm trong mô đun. Phần trăm hiện `16,1%`.

Filter phải có unit test riêng, gồm số 0, số tròn nghìn, và cả ba mức thập phân.

Với `value_mode = money`, đơn vị là VNĐ và `decimal_places = 0`.

---

## 4. Xoá cứng ba cấp (mục 7 của người dùng)

### Hành vi

Xoá một hạng mục → xoá toàn bộ phiếu của nó.
Xoá một khu vực → xoá toàn bộ hạng mục và phiếu bên trong.
Xoá một loại tiến độ → xoá toàn bộ khu vực, hạng mục, phiếu bên trong.

FK đang là `ondelete="RESTRICT"`, nên service phải xoá tường minh theo thứ tự
phiếu → hạng mục → khu vực → loại, **trong một transaction**. Không dựa vào
cascade của database.

### Ghi audit trước khi xoá

Trước khi xoá, chụp lại toàn bộ nội dung sẽ mất vào `old_values` của một bản ghi
audit: tên các cấp, và với từng phiếu là ngày, khối lượng, ghi chú, người tạo.
Action: `construction_progress.type.delete`, `.group.delete`, `.item.delete`.

Đây là điều kiện để việc xoá vẫn truy vết được — không có nó thì dữ liệu biến mất
không dấu vết, trái yêu cầu của `CLAUDE.md` về mutation phải attributable.

### Hộp thoại xác nhận

Hiện chính xác những gì sẽ mất, ví dụ:

> Xoá khu vực **Tầng hầm** sẽ xoá vĩnh viễn 4 hạng mục và 37 phiếu cập nhật.
> Không thể hoàn tác. Gõ `Tầng hầm` để xác nhận.

Server **phải kiểm lại tên đã gõ** qua một trường `confirm_name`, và trả 400 nếu
không khớp. Nhờ vậy một POST mù không thể xoá được, và điều này test được.

### Quyền

Yêu cầu `can_manage_progress_structure` ở cấp dự án và
`construction_progress.structure` ở cấp RBAC — giống hành động sửa. Xoá phiếu đơn
lẻ giữ nguyên quy tắc hiện tại theo chủ sở hữu.

---

## 5. Dọn dữ liệu ẩn và bỏ cột `is_active` (mục 8)

1. Sau khi Bước 2 xong, dùng UI xoá hết các loại tiến độ / khu vực / hạng mục đang
   ẩn. Ghi lại đã xoá những gì vào báo cáo cuối.
2. Bỏ mọi nút "Ẩn" và mọi route archive khỏi mô đun.
3. Bỏ mọi điều kiện `is_active` trong truy vấn của mô đun, gồm cả phần đếm
   `summaries["progress"]` ở `project_workspace()`.
4. Migration xoá cột `is_active` khỏi `progress_types`, `progress_groups`,
   `progress_items`, với guard ở đầu `upgrade()`:

   ```
   nếu tồn tại hàng nào is_active = false  ->  raise, nêu rõ bảng và số lượng
   ```

   `downgrade()` thêm lại cột với `server_default` true.

---

## 6. Overlay tạo và sửa khu vực (mục 1 và 2)

### Tạo khu vực kèm hạng mục — một overlay

Nút "Thêm khu vực" mở overlay gồm:

- Tên khu vực.
- Danh sách hàng hạng mục, mỗi hàng: tên, đơn vị, số chữ số thập phân, khối lượng
  kế hoạch, khối lượng đã làm trước khi dùng hệ thống.
- Nút "Thêm hạng mục" thêm một hàng trống. Cho phép tạo khu vực không có hạng mục
  nào.
- Một nút lưu duy nhất.

Route mới: `POST .../types/<type_id>/groups/batch`. Một transaction. Trùng tên
hạng mục trong cùng payload phải bị chặn ở server, không chỉ ở client.

### Sửa khu vực kèm hạng mục — overlay riêng

Nút "Sửa" trên mỗi khu vực mở overlay tương tự, đã điền sẵn:

- Đổi tên khu vực.
- Sửa từng hạng mục đang có.
- Thêm hạng mục mới.
- Đánh dấu hạng mục để xoá. Hàng bị đánh dấu phải hiện ngay "sẽ xoá N phiếu".
  Khi có ít nhất một hàng bị đánh dấu, cần một checkbox xác nhận duy nhất cho cả
  lượt và nút lưu chuyển sang kiểu cảnh báo.

Route mới: `POST .../groups/<group_id>/batch`. Một transaction cho toàn bộ đổi
tên, sửa, thêm, và xoá.

Việc gõ tên để xác nhận chỉ áp dụng khi xoá cả một khu vực hoặc cả một loại; xoá
hạng mục lồng trong overlay sửa dùng checkbox như trên.

---

## 7. Overlay phiếu cập nhật ngày hàng loạt (mục 4)

Thay thế cách làm hiện tại là phải vào từng hạng mục.

Nút **"Tạo phiếu cập nhật ngày"** ở đầu trang chi tiết loại, mở overlay gồm:

- **Một ô ngày duy nhất** cho cả phiếu, chặn ngày tương lai theo `local_today()`.
- Nhiều dòng, mỗi dòng: dropdown khu vực → dropdown hạng mục (chỉ hiện hạng mục
  thuộc khu vực đã chọn) → khối lượng trong ngày → ghi chú.
- Nút "Thêm dòng".
- **Không bắt buộc điền hết** khu vực hay hạng mục. Chỉ dòng nào có nhập mới tạo
  phiếu.
- Nút lưu: "Tạo phiếu cập nhật ngày".

Route mới: `POST .../types/<type_id>/entries/batch`.

Kiểm tra ở server, tất cả trong một transaction:

| Điều kiện | Xử lý |
|---|---|
| `item_id` không thuộc loại/dự án trên URL | 404, không lộ tên |
| Hai dòng cùng một `item_id` | Chặn, nêu rõ hạng mục bị trùng |
| Hạng mục đã có phiếu cho ngày đó | Chặn, nêu rõ dòng nào và ngày nào |
| `quantity <= 0` | Chặn theo dòng |
| Số chữ số thập phân vượt `decimal_places` | Chặn theo dòng |
| Ngày tương lai | Chặn cả phiếu |

Sai bất kỳ dòng nào thì **không lưu gì cả**, và overlay hiện lại với đúng dữ liệu
người dùng đã nhập cùng thông báo theo từng dòng. Không được mất dữ liệu đã nhập.

Mỗi phiếu tạo ra vẫn ghi một bản ghi audit `construction_progress.entry.create`
như hiện tại. Mỗi hạng mục bị ảnh hưởng được tính lại `completed_quantity` một lần
trong cùng transaction, vẫn theo cách cộng lại từ tổng phiếu.

Form tạo phiếu ở trang chi tiết hạng mục **giữ nguyên** — nó vẫn tiện khi chỉ cập
nhật một hạng mục.

---

## 8. Bỏ biểu đồ khỏi trang chi tiết (mục 6)

Xoá canvas biểu đồ khỏi `type_detail.html`, xoá
`app/static/js/construction-progress.js` và `tests_js/construction-progress.test.js`.

**Giữ lại** route `.../chart-data` cùng toàn bộ test phân quyền của nó — phase
dashboard sau này sẽ dùng. Ghi rõ điều này trong báo cáo để không ai xoá nhầm.

Biểu đồ hiện cũng đang vỡ layout, cao vô hạn vì canvas không bị giới hạn chiều
cao. Không cần sửa vì đang bỏ đi, nhưng khi làm dashboard phải bọc canvas trong
một div có chiều cao xác định và `maintainAspectRatio: false`.

---

## 9. UI/UX (mục 3)

Nguyên nhân chính không phải thiếu CSS. Hiện `type_detail.html` render **form sửa
luôn hiện thẳng trong bảng**: mỗi hạng mục có một hàng dữ liệu rồi ngay dưới là một
hàng gồm bốn ô input và hai nút. Bảng vì thế bị nhân đôi số hàng và không thể căn
chỉnh. Khi mọi form chuyển vào overlay ở mục 6 và 7, phần lớn vấn đề tự hết.

Sau khi các overlay xong, làm nốt:

- Bảng cây chỉ còn dữ liệu: khu vực / hạng mục, đơn vị, kế hoạch, đã làm, phần
  trăm, thanh tiến độ, nút hành động. **Không còn ô input nào trong bảng.**
- Mọi cột số **căn phải**, dùng `vn_number`, đơn vị đứng riêng một cột.
- Khu vực gập/mở được, mặc định mở.
- Hạng mục chưa khai kế hoạch hiện `—` kèm nhãn "chưa có kế hoạch".
- Hạng mục vượt kế hoạch: thanh tiến độ dừng ở 100%, kèm nhãn "vượt kế hoạch
  +N%". Con số thật vẫn hiện ở cột đã làm.
- Nhóm nút hành động thống nhất, dùng lại lớp Bootstrap sẵn có trong repo, không
  thêm CSS riêng cho mô đun nếu tránh được.
- Khớp mật độ và khoảng cách với `project_operations/*.html` để không lệch phần
  còn lại của hệ thống.

---

## 10. Kế hoạch thi hành

Tám bước, mỗi bước một commit, mỗi commit `pytest` xanh. **Ngân sách pytest ít
nhất 20 phút** — suite khoảng 6 phút, đừng cắt ở 60 giây.

| Bước | Nội dung | Lý do xếp ở đây |
|---|---|---|
| 0 | Mốc xanh: `pytest -q --durations=10`, `npm test`, ghi vào `BASELINE_12_1.md` | Không có mốc thì mọi test đỏ sau này không quy được trách nhiệm |
| 1 | `decimal_places` + filter `vn_number` + validation nhập + áp dụng toàn bộ hiển thị | Lỗi đọc sai 1000 lần, ưu tiên cao nhất |
| 2 | Xoá cứng ba cấp: service, route, audit, `confirm_name`, test | Mở đường cho Bước 3 |
| 3 | Dọn bản ghi đang ẩn, bỏ nút/route Ẩn, migration xoá `is_active` có guard | Phải sau Bước 2, xem mục 2 |
| 4 | Overlay tạo khu vực kèm hạng mục + overlay sửa | Thay form inline, gốc của UI xấu |
| 5 | Overlay phiếu ngày hàng loạt | Thay đổi lớn nhất về luồng người dùng |
| 6 | Bỏ biểu đồ khỏi trang chi tiết | Nhỏ, độc lập |
| 7 | Trau UI/UX toàn mô đun | Sau khi overlay đã dọn sạch bảng |
| 8 | Chốt: cập nhật `PHASE12_RESULT.md` thêm mục 10, ghi việc phải làm khi deploy | |

Cổng dừng: sau **Bước 3** báo cáo trước khi làm overlay — vì đó là chỗ có migration
và xoá dữ liệu thật. Sau **Bước 5** báo cáo trước khi trau UI.

### File được phép sửa

```
app/models/progress.py                     decimal_places, bỏ is_active
app/models/__init__.py
app/construction_progress/services.py      xoá cứng, batch, validation thập phân
app/construction_progress/routes.py        route batch và delete, bỏ archive
app/templates/construction_progress/*.html overlay và bảng
app/ui.py  hoặc nơi đăng ký Jinja filter   vn_number
app/project_operations/routes.py           bỏ điều kiện is_active ở summaries
migrations/versions/<hash>_*.py            hai migration: decimal_places, drop is_active
tests/test_construction_progress_*.py
tests/test_vn_number.py                    hoặc thêm vào file test filter sẵn có
```

Xoá: `app/static/js/construction-progress.js`,
`tests_js/construction-progress.test.js`.

Cấm chạm: `app/config.py`, `pytest.ini`, `docker-compose.yml`, `.audit/**`,
`app/auth/permissions.py` (không cần thêm quyền mới),
`project_read_required`/`project_write_required`/`project_manage_required`/`can_write_project`.

### Kiểm thử bắt buộc thêm so với Phase 12

- `vn_number`: 0, số tròn nghìn, ba mức thập phân, và số âm nếu có thể xảy ra.
- Nhập quá số chữ số thập phân cho phép → chặn, ở cả hạng mục và phiếu.
- Xoá cứng từng cấp: đúng số hàng con biến mất, audit có `old_values` chứa nội dung
  phiếu đã xoá, và `confirm_name` sai → 400 mà **không xoá gì**.
- Xoá cứng khi không có `can_manage_progress_structure` → 403, không xoá gì.
- Migration drop `is_active`: guard fail khi còn hàng ẩn (test bằng cách tạo một
  hàng ẩn rồi gọi migration trên DB dùng một lần).
- Batch khu vực: trùng tên trong payload → chặn, không tạo hàng nào.
- Batch phiếu: mọi dòng trong bảng ở mục 7, và khẳng định **không hàng nào** được
  tạo khi một dòng sai.
- Batch phiếu thành công nhiều dòng → `completed_quantity` và phần trăm ba cấp đúng
  cho từng hạng mục bị ảnh hưởng.
- Overlay giữ lại dữ liệu người dùng đã nhập khi có lỗi.

Assertion tiếng Việt dùng `get_data(as_text=True)`, **không** dùng byte literal
`b"..."`. Chốt: `grep -rn '\x' tests/test_construction_progress_*.py` phải rỗng.

### Ngoài phạm vi

Dashboard và biểu đồ (làm ở phase sau, route `chart-data` giữ lại cho nó), import
Excel, ảnh đính kèm cho phiếu, biểu đồ đường lũy kế, duyệt phiếu, và test đồng thời
trên PostgreSQL cho mô đun tiến độ (đang có task riêng).

---

## 11. Điều kiện trước khi dùng xoá cứng trên production

Ba điều kiện. Điều kiện 1 nằm trong phạm vi Phase 12.1; hai điều kiện còn lại là
việc vận hành và một tính năng dùng chung, **không** thuộc phase này nhưng phải xong
trước khi người dùng thật được phép xoá.

1. **Audit chụp đủ nội dung trước khi xoá.** Yêu cầu ở mục 4. Nếu `old_values`
   không chứa đủ để dựng lại phiếu đã xoá (ngày, khối lượng, ghi chú, người tạo),
   thì việc xoá là mất dữ liệu không dấu vết.

2. **Backup tự động đã từng được thử restore thành công.** Cơ chế đã có:
   `scripts/backup_db.sh`, `scripts/restore_db.sh`, và systemd timer trong
   `deploy/systemd/`. `DEPLOY_UBUNTU.md:137-142` yêu cầu cài timer và "test a
   restore in isolation" bằng tay. Phải xác nhận timer đã enable trên server thật
   **và** đã restore thử ít nhất một lần. Backup chưa từng restore là niềm tin,
   không phải bảo hiểm.

3. **Có màn hình xem audit log trong phần quản trị.** Hiện `AuditLog` được ghi đầy
   đủ nhưng **không có route hay template nào trong `app/admin/` để đọc nó**. Với
   trạng thái đó, "vẫn truy vết được ai xoá gì" chỉ đúng với người truy cập được
   SQL — trong khi người cần biết "ai xoá 37 phiếu của Tầng hầm" là quản lý dự án.

   Xoá cứng mà không ai đọc được audit thì về mặt vận hành giống hệt xoá không dấu
   vết. Đây là tính năng dùng chung cho toàn hệ thống, không riêng mô đun tiến độ,
   nên làm ở task riêng: lọc theo dự án / hành động / người thực hiện / khoảng
   thời gian, xem được `old_values` và `new_values`, chỉ dành cho quản trị.

## 12. Khi nào phải xem lại quyết định xoá cứng

Quyết định ở mục 1 dựa trên một điều kiện cụ thể: khối lượng **không** dẫn tới tiền.
Phải mở lại thiết kế nếu bất kỳ điều nào sau đây xảy ra:

- Khối lượng được dùng cho nghiệm thu, thanh toán, hoặc đối chiếu hợp đồng với chủ
  đầu tư hay nhà thầu.
- Số liệu tiến độ được xuất ra tài liệu gửi ra ngoài công ty và có thể bị tranh chấp.
- Có yêu cầu lưu trữ theo quy định đối với hồ sơ tiến độ.

Khi đó mô hình đúng **không phải** xoá mềm mà là **chỉ thêm, không sửa**: nhập sai
thì ghi một phiếu điều chỉnh, phiếu gốc giữ vĩnh viễn; "sửa phiếu" và "xoá phiếu"
biến mất khỏi giao diện. Cấu trúc (loại, khu vực, hạng mục) vẫn xoá cứng bình thường
trong cả hai mô hình — chỉ phiếu là bất biến.

Ghi chú kỹ thuật cho lần chuyển đó: vì audit đã chụp đủ nội dung phiếu trước khi
xoá (mục 4), lịch sử vẫn dựng lại được. Nhưng chuyển sang mô hình chỉ-thêm sẽ cần
migration và soát lại toàn bộ cách tính lũy kế, nên không phải việc làm trong một
patch nhỏ.
