# Phase 14 — Mở rộng vấn đề tồn đọng thành nhiều hạng mục

Vấn đề tồn đọng hiện là một bản ghi phẳng: một tiêu đề, một mức độ, một trạng thái, một hạn xử
lý, một người phụ trách. Thực tế một vấn đề như "Chậm tiến độ tầng hầm B2" thường gồm nhiều mặt
khác nhau — an toàn, vật tư, thi công — mỗi mặt có mức độ, hạn và người phụ trách riêng, và tiến
triển độc lập.

Phase này cho một vấn đề chứa **nhiều hạng mục**, dùng lại đúng danh mục hạng mục của Báo cáo
ngày.

## 0. Quyết định đã chốt, và lý do

Sáu quyết định dưới đây do chủ dự án chốt. Ghi cả lý do để người sau không sửa ngược mà không
biết mình đang bỏ điều gì.

### 0.1. Mức độ tổng nhập tay, độc lập với hạng mục

Mức độ của cả vấn đề là **đánh giá chung của người tạo**, không tính từ các hạng mục.

Hệ quả có chủ ý: sẽ có lúc vấn đề ghi "Thấp" mà bên trong có hạng mục "Nghiêm trọng".
**Không thêm cảnh báo, không chặn.** Người tạo có thể có lý do — ví dụ hạng mục nghiêm trọng đã
có phương án xử lý chắc chắn. Đây là hành vi có chủ ý, không phải lỗi.

### 0.2. Trạng thái tổng tự tính, không sửa được

Không có ô chọn trạng thái ở cấp vấn đề. Trạng thái suy ra từ các hạng mục theo §2.

### 0.3. Bỏ toàn bộ nút "Đóng"

Không còn nút đóng hay mở lại ở bất kỳ đâu — không ở màn danh sách, không ở trang chi tiết. Việc
đóng chỉ làm bằng cách đổi **trạng thái của từng hạng mục**.

Lý do: khi trạng thái tổng là giá trị tự tính, một nút đóng tay là mâu thuẫn — bấm xong hệ thống
tính lại và mở ra.

### 0.4. Bỏ cột "Phụ trách" khỏi màn hình danh sách vấn đề

Mỗi hạng mục có người phụ trách riêng, nên một cột duy nhất ở cấp vấn đề không diễn tả được gì.
Người phụ trách chỉ hiện ở từng hạng mục trong trang chi tiết.

### 0.5. Một loại hạng mục chỉ xuất hiện một lần trong mỗi vấn đề

Giống ràng buộc `uq_daily_report_sections_report_category` của Báo cáo ngày (đã xác minh: UNIQUE
trên `(daily_report_id, report_category_id)`, và dữ liệu thật có max 1 hạng mục mỗi loại mỗi báo
cáo).

Hai lý do. **Một**, nếu cho phép trùng thì mỗi hạng mục cần thêm trường tiêu đề riêng để phân
biệt, mà đặc tả này không có — tên loại hạng mục chính là nhãn của khối. **Hai, và quan trọng
hơn: nới một ràng buộc UNIQUE về sau thì dễ, siết lại sau khi đã có dữ liệu trùng thì không có
cách nào đúng để chọn giữ hàng nào.**

### 0.6. Bốn cột tổng hợp vẫn nằm trên bảng `persistent_issues`

Hạng mục giữ sự thật, nhưng `severity`, `status`, `due_date`, `closed_date` vẫn **lưu sẵn** ở cấp
vấn đề và được tính lại mỗi lần một hạng mục thay đổi.

Lý do đã xác minh: màn hình danh sách vấn đề **hiển thị** các cột `MỨC ĐỘ`, `TRẠNG THÁI`,
`HẠN XỬ LÝ`. Không lưu sẵn thì mỗi dòng phải join và tính tổng hợp qua các hạng mục.

Lưu ý: lý do **không** phải là bộ lọc. Đã kiểm — không có ô lọc nào trên màn danh sách, và cũng
không có link lọc nào trên dashboard dự án. Xem §6.

Tiền lệ trong repo: `ProgressItem.completed_quantity` là giá trị lũy kế lưu sẵn, tính lại mỗi
lần ghi phiếu, kèm một phép kiểm bất biến trong `scripts/verify_progress_module.py`. Phase này
làm y hệt.

---

## 1. Mô hình dữ liệu

### 1.1. Bảng mới `persistent_issue_sections`

Dựng song song với `daily_report_sections`.

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `id` | BigInteger PK | |
| `persistent_issue_id` | FK → `persistent_issues.id` | có index |
| `report_category_id` | FK → `report_categories.id` | có index, **dùng chung với Báo cáo ngày** |
| `severity` | String | giá trị của `IssueSeverity` |
| `status` | String | giá trị của `IssueStatus` |
| `due_date` | Date, nullable | Hạn xử lý |
| `owner_user_id` | FK → `users.id`, nullable | Người phụ trách |
| `description` | Text, nullable | Mô tả vấn đề |
| `proposed_solution` | Text, nullable | Đề xuất giải pháp |
| `sort_order` | Integer | thứ tự hiển thị |
| `created_by_id` | FK → `users.id` | **bắt buộc gán** — xem 1.3 |
| `updated_by_id` | FK → `users.id`, nullable | **bắt buộc gán khi sửa** |
| `created_at`, `updated_at` | DateTime | |
| `deleted_at` | DateTime, nullable | xoá mềm |

**Ràng buộc UNIQUE** `(persistent_issue_id, report_category_id)` theo §0.5. Đặt tên theo khuôn
đang có: `uq_persistent_issue_sections_issue_category`.

`sort_order` phải được **gán giá trị thật**, không để mặc định 0 cho mọi hàng. Phase 12 đã mắc
lỗi này: `display_order` tồn tại từ đầu nhưng không ai gán, nên thứ tự hạng mục nhảy loạn sau mỗi
lần cập nhật và chỉ phát hiện ra khi test tay với 15 hạng mục. Quan hệ trong model phải khai
`order_by` tường minh, gồm cả `id` làm tiebreaker.

### 1.2. Thay đổi trên bảng `persistent_issues`

**Giữ lại và tiếp tục dùng:** `title`, `project_id`, `opened_date`, `description`,
`severity` (nhập tay theo §0.1), `created_by_user_id`, `created_at`, `updated_at`, `deleted_at`.

**Giữ lại nhưng chuyển thành giá trị tự tính:** `status`, `due_date`, `closed_date`.

**Bỏ:** `owner_user_id`. Dữ liệu của nó được chuyển vào hạng mục sinh ra ở §5 trước khi bỏ cột.

Về việc bỏ cột: `downgrade` của migration phải **tạo lại cột và điền lại** từ hạng mục tương ứng.
Chỉ có 3 hàng nên kiểm được cả hai chiều bằng mắt. Không để lại cột chết — Phase 13 đã tốn công
vì `Project.created_by_user_id` tồn tại mà không ai gán.

### 1.3. Không audit việc tạo, vì bảng tự ghi người tạo

Bảng mới có `created_by_id` và **phải thực sự được gán** khi tạo hạng mục. Vì vậy **không** thêm
action `issue.section.create` vào audit.

Đây là luật đã áp trong Phase 13: nếu bảng đích ghi được người tạo thì bản ghi tự nó là chứng cứ,
không cần hàng audit. Nếu bảng không ghi được thì mới phải audit. Bảy action `.create` được giữ
lại trong Phase 13 đều vì bảng đích **không** có cột người tạo.

**Phải tự kiểm sau khi làm:** tạo một hạng mục rồi truy vấn xem `created_by_id` có giá trị thật
hay không. Đừng chỉ khai cột rồi tin là nó được gán.

---

## 2. Quy tắc tổng hợp

Tính lại mỗi lần một hạng mục được tạo, sửa, hoặc xoá mềm. Viết thành **một hàm duy nhất**, ví
dụ `recalculate_issue_rollup(issue)`, đặt trong `app/issues/services.py`. Không rải logic ra
nhiều chỗ.

Gọi tập hạng mục "đang mở" là các hạng mục có `deleted_at IS NULL` và `status` thuộc
`{OPEN, PROCESSING}`.

### 2.1. `status`

- Nếu **không có** hạng mục nào (mới tạo vấn đề, chưa thêm hạng mục) → `OPEN`.
- Nếu **mọi** hạng mục chưa xoá đều có `status` thuộc `{RESOLVED, CLOSED}` → `CLOSED`.
- Ngược lại, nếu có bất kỳ hạng mục `PROCESSING` → `PROCESSING`.
- Còn lại → `OPEN`.

Thứ tự kiểm là bắt buộc: kiểm "tất cả đã xong" **trước** khi kiểm "có cái đang xử lý".

Đây là quy tắc an toàn theo hướng "vẫn mở": sai theo hướng vẫn mở thì việc còn tồn đọng vẫn nằm
trong danh sách; sai theo hướng đã đóng thì nó biến khỏi tầm mắt.

### 2.2. `due_date`

Hạn **sớm nhất** trong các hạng mục đang mở có `due_date` khác rỗng. Nếu không có hạng mục nào
đang mở, hoặc không hạng mục nào khai hạn → `NULL`.

### 2.3. `closed_date`

Khi `status` chuyển thành `CLOSED` và `closed_date` đang rỗng → đặt bằng ngày hôm nay (dùng
`local_today()` như `app/issues/services.py` đang dùng).

Khi `status` rời khỏi `CLOSED` → xoá `closed_date` về `NULL`.

### 2.4. `severity` — KHÔNG tính

Nhắc lại cho rõ vì đây là chỗ dễ làm sai theo bản năng: mức độ tổng **nhập tay**, hàm tổng hợp
**không được** ghi vào `severity`. Nếu hàm của bạn có dòng nào gán `issue.severity` thì đã sai.

### 2.5. Bất biến phải kiểm được

Thêm phép kiểm vào `scripts/verify_progress_module.py`, hoặc tạo
`scripts/verify_issue_rollup.py` theo cùng khuôn (chỉ đọc, mã thoát 1 khi có vi phạm):

- Với mọi vấn đề chưa xoá: `status` khớp đúng quy tắc §2.1 khi tính lại từ hạng mục thật.
- `due_date` khớp §2.2.
- `closed_date` khác rỗng khi và chỉ khi `status == CLOSED`.
- Không vấn đề nào có hai hạng mục cùng `report_category_id`.

Unit test chạy trên dữ liệu giả nên không phát hiện được dữ liệu thật đã lệch bất biến sau một
lần retry hay một lần sửa tay. Script này kiểm đúng chỗ đó.

---

## 3. Giao diện

### 3.1. Biểu mẫu tạo và sửa

**Khối tổng quan** — chỉ gồm: Tiêu đề, Dự án, Ngày mở, **Mức độ tổng**, Mô tả tổng quan.

Không có ô Trạng thái, không có ô Hạn xử lý, không có ô Người phụ trách. Hiện một dòng chú thích
tiếng Việt nói rõ trạng thái và hạn xử lý được tính từ các hạng mục bên dưới — nếu không, người
dùng sẽ đi tìm hai ô đó.

**Các khối hạng mục** — mỗi khối gồm ô chọn loại hạng mục, rồi Mức độ, Trạng thái, Hạn xử lý,
Người phụ trách, Mô tả vấn đề, Đề xuất giải pháp. Có nút xoá hạng mục.

**Nút "+ Thêm hạng mục"** ở dưới các khối. Khi bấm, một khối mới hiện ra ở trạng thái chỉ có ô
chọn loại hạng mục; các trường còn lại hiện sau khi đã chọn loại.

Ô chọn loại hạng mục **không được liệt kê loại đã dùng trong vấn đề này** — đó là cách thực thi
§0.5 ở phía giao diện. Nhưng phải **kiểm lại ở server**: một request gửi tay vẫn có thể trùng, và
ràng buộc UNIQUE ở database là hàng phòng ngự cuối.

### 3.2. Danh mục hạng mục dùng chung — ba hệ quả

Bảng `report_categories` có `project_id`, nên danh mục theo từng dự án. Chỉ liệt kê hạng mục của
đúng dự án đang xem, và chỉ hạng mục `is_active`.

**Một: cờ `is_required` chỉ áp cho Báo cáo ngày.** Vấn đề tồn đọng **không** bị ép phải có đủ
hạng mục bắt buộc. Hiện 12 hạng mục của dự án 1 đều `is_required = false` nên chưa xung đột, nhưng
phải viết rõ để sau này ai bật cờ đó cho Báo cáo ngày thì không vô tình ép cả vấn đề tồn đọng.

**Hai: hạng mục bị tắt vẫn phải hiện được.** Nếu một loại hạng mục bị chuyển `is_active = false`
sau khi đã có hạng mục vấn đề tham chiếu nó, trang chi tiết vẫn phải render bình thường. Chỉ ẩn
nó khỏi danh sách **chọn mới**. Báo cáo ngày đã xử lý tình huống này — dùng lại đúng cách đó.

**Ba: đổi tên một loại hạng mục ảnh hưởng cả hai mô đun.** Đây là hành vi đã được chấp nhận cho
Báo cáo ngày; ghi lại để không ai bất ngờ.

### 3.3. Màn hình danh sách

Bỏ cột `PHỤ TRÁCH` theo §0.4. Bỏ nút `Đóng` theo §0.3.

Giữ các cột `TIÊU ĐỀ`, `DỰ ÁN`, `MỨC ĐỘ`, `TRẠNG THÁI`, `NGÀY MỞ`, `HẠN XỬ LÝ`. Ba cột sau đọc
từ giá trị lưu sẵn theo §0.6.

Thêm một cột hoặc một chỉ dấu cho **số hạng mục**, ví dụ "3 hạng mục" — vì bây giờ hai vấn đề
cùng mức độ có thể khác nhau rất nhiều về khối lượng.

### 3.4. Trang chi tiết

Khối tổng quan ở trên, danh sách hạng mục ở dưới, xếp theo `sort_order` rồi `id`.

Mỗi hạng mục hiện đủ Mức độ, Trạng thái, Hạn xử lý, Người phụ trách, Mô tả vấn đề, Đề xuất giải
pháp.

Hạng mục đã đóng nên phân biệt được bằng mắt với hạng mục đang mở.

---

## 4. Bỏ nút đóng và sửa audit

Đây là bước dễ bỏ sót nhất của phase. Phase 13 vừa xây audit log và vừa xác minh
`issue.close`/`issue.reopen` phát đúng — phase này làm hai emitter đó biến mất.

### 4.1. Xoá

- Route `POST /<issue_id>/close` — `app/issues/routes.py:128`
- Route `POST /<issue_id>/reopen` — `app/issues/routes.py:138`
- Hàm `close_issue()` — `app/issues/services.py:72`
- Hàm `reopen_issue()` — `app/issues/services.py:80`
- Nút trong `app/templates/issues/index.html`

**Không xoá** route `/delete` và hàm `delete_issue()` (`app/issues/services.py:88`) — việc xoá
vấn đề vẫn giữ, và `tests/test_phase10_cleanup_delete.py` đang phủ nó.

### 4.2. Action audit mới ở cấp hạng mục

Việc đóng và mở lại giờ xảy ra khi đổi trạng thái một hạng mục. Cần:

| Action | Nhóm | Vì sao phải khai tường minh |
|---|---|---|
| `issue.section.close` | `mutation` | **không khớp luật hậu tố nào** → sẽ rơi vào `retain_forever` nếu quên |
| `issue.section.reopen` | `mutation` | cùng lý do |
| `issue.section.update` | `mutation` | luật hậu tố `.update` đã bao |
| `issue.section.delete` | `destructive` | luật hậu tố `.delete` đã bao |

Bảng ánh xạ ở `app/audit.py` áp ba tầng theo thứ tự: ngoại lệ tường minh → luật hậu tố → mặc định
`retain_forever`. Hai action `.close` và `.reopen` phải nằm ở **tầng ngoại lệ**, cạnh
`issue.close` và `issue.reopen` đang có.

Quy tắc phát giống cấp vấn đề trước đây: khi một lần sửa hạng mục có chuyển trạng thái đóng/mở
thì phát `issue.section.close` hoặc `issue.section.reopen` **thay cho** `issue.section.update`;
chỉ sửa trường khác thì phát `issue.section.update`. **Không phát cả hai cho một lần sửa** — hai
hàng cho một hành động làm trang xem audit đếm sai.

Snapshot của `issue.section.delete` phải đủ để dựng lại: loại hạng mục, mức độ, trạng thái, hạn,
người phụ trách, mô tả, đề xuất giải pháp, `created_at`, `created_by_id`. Phase 13 đã làm giàu
snapshot cho mọi action phá dữ liệu — đừng để action mới thành ngoại lệ nghèo nàn.

### 4.3. `issue.close` và `issue.reopen` thành action lịch sử

Sau khi xoá hai route, hai action này **không còn emitter** nhưng vẫn có hàng lịch sử trong bảng
`audit_logs`. Giữ chúng trong bảng ánh xạ, **kèm chú thích trong code** rằng đây là action lịch
sử không còn emitter, việc đóng đã chuyển xuống cấp hạng mục từ Phase 14.

Đây đúng khuôn đã dùng cho `partner.deactivate` — người sau đọc bảng ánh xạ sẽ không đi tìm
emitter vô ích.

### 4.4. Việc tự động đóng vấn đề tổng có audit không?

**Không.** Trạng thái tổng là hệ quả tính toán, không phải hành động của người dùng. Hành động
thật là việc đóng hạng mục cuối cùng, và nó đã được audit. Thời điểm đóng vấn đề đọc được từ
`closed_date`.

Ghi rõ quyết định này vào tài liệu kết quả, vì nó là câu hỏi hợp lý mà người sau sẽ đặt.

---

## 5. Chuyển đổi dữ liệu

Dữ liệu hiện có rất nhỏ: **3 vấn đề tồn đọng** (1 chưa xoá), cả 3 đều có `severity`, 2 có
`owner_user_id`, 3 có `due_date`.

Với mỗi vấn đề đang có, migration sinh **một** hạng mục mang toàn bộ giá trị cũ:

- `severity`, `status`, `due_date`, `owner_user_id` sao y từ vấn đề
- `description` của hạng mục: sao từ `description` của vấn đề, hoặc để rỗng và giữ mô tả ở cấp
  vấn đề — **chọn một và ghi rõ**, đừng nhân đôi cùng một đoạn văn ở hai chỗ
- `report_category_id`: dùng hạng mục đầu tiên theo `sort_order` của dự án đó. Nếu dự án không có
  hạng mục nào `is_active` thì **dừng migration với lỗi rõ ràng**, đừng đoán
- `created_by_id`: lấy `created_by_user_id` của vấn đề; nếu rỗng thì để rỗng, **đừng bịa**
- `sort_order`: 0

Sau đó bỏ cột `owner_user_id` khỏi `persistent_issues`, và tính lại `status`/`due_date`/
`closed_date` theo §2 cho cả 3 hàng.

`downgrade` phải: tạo lại cột `owner_user_id`, điền lại từ hạng mục tương ứng, rồi xoá bảng mới.
Với 3 hàng thì kiểm được cả hai chiều bằng mắt — **hãy kiểm thật**, đừng chỉ viết.

### 5.1. Xác minh trên PostgreSQL thật, vì test không chạy migration

Test dựng schema bằng `db.create_all()` nên **không chạy migration**. Phải tự chạy đủ vòng này
trên database development và dán kết quả vào phần trả lời:

```
flask db upgrade
psql -d construction_relation_management -c "SELECT count(*) FROM persistent_issue_sections;"
psql -d construction_relation_management -c "SELECT id, status, due_date, closed_date FROM persistent_issues;"
flask db downgrade
psql -d construction_relation_management -c "SELECT column_name FROM information_schema.columns WHERE table_name='persistent_issues' AND column_name='owner_user_id';"
flask db upgrade
```

Sau `downgrade`, cột `owner_user_id` phải quay lại và có đúng giá trị cũ. `downgrade` hỏng là thứ
chỉ phát hiện ra lúc cần rollback production.

Kiểm chuỗi migration: `down_revision` trỏ đúng head hiện tại, và sau khi thêm còn **đúng một
head**. Chạy `flask db heads` để xác nhận.

---

## 6. Dọn bộ lọc vấn đề

Hiện trạng đã xác minh:

- Có **hai** hàm `_apply_issue_filters` gần trùng nhau: `app/issues/routes.py:195` và
  `app/projects/routes.py:316`. Chúng cho kết quả **giống nhau** hôm nay (một bên dùng chuỗi
  `"CRITICAL"`, một bên dùng `DailyReportStatus.CRITICAL.value`, mà giá trị enum trùng chuỗi).
- **Không có ô lọc nào** trên màn hình danh sách vấn đề, và **không có link lọc nào** trên
  dashboard dự án. Bộ lọc chỉ chạy khi có người tự gõ tham số vào URL.

Việc cần làm:

**Gộp hai hàm thành một**, đặt ở nơi cả hai chỗ dùng được. Sửa một bên mà quên bên kia sẽ làm hai
màn hình lệch nhau âm thầm — và Phase 14 chính là lần sửa đó.

**Thêm ô lọc thật** trên màn hình danh sách vấn đề, vì code lọc đang tồn tại mà không ai dùng
được. Các tiêu chí nên có sau Phase 14: mức độ, trạng thái, khoảng ngày mở, và **loại hạng mục** —
tiêu chí cuối là năng lực mới mà hạng mục mở ra, cho phép hỏi "những vấn đề nào có mặt An toàn".

Lọc theo loại hạng mục là truy vấn qua bảng con, nên phải dùng `EXISTS` hoặc join có
`DISTINCT` — cẩn thận không nhân bản dòng khi một vấn đề có nhiều hạng mục khớp.

Mọi tiêu chí lọc nằm trong URL để chia sẻ được và bấm Back đúng, giống cách
`app/construction_progress/routes.py` làm với `_entry_list_state()`.

---

## 7. Phân quyền

**Không thêm quyền mới, không thêm capability mới.** Hạng mục thuộc về vấn đề, nên quyền trên
hạng mục **bằng đúng** quyền trên vấn đề chứa nó.

Dùng lại các helper đang có trong `app/auth/permissions.py`. Đừng tạo tầng phân quyền thứ hai.

Điểm phải kiểm cẩn thận: mọi route ở cấp hạng mục nhận `section_id` từ URL đều phải xác minh hạng
mục đó **thuộc về** một vấn đề mà người dùng được phép sửa. Đây là lỗi confused-deputy kinh điển:
id vấn đề hợp lệ ghép với id hạng mục của dự án khác.

Test bắt buộc: người dùng có quyền trên dự án 1 gửi `section_id` của một hạng mục thuộc dự án 2 →
**404**, và không có thay đổi nào trong database.

---

## 8. Các bước thực hiện, có cổng dừng

| Bước | Nội dung | Vì sao đặt ở đây |
|---|---|---|
| 0 | Mốc xanh: chạy `pytest` đầy đủ, ghi số liệu. Baseline hiện tại **745 passed, 3 skipped** | Không có mốc thì test đỏ sau này không quy được trách nhiệm |
| 1 | Model `PersistentIssueSection` cộng migration cộng chuyển đổi dữ liệu §5. Chưa có giao diện | Dữ liệu phải đúng trước khi có gì đọc nó |
| 2 | Hàm tổng hợp §2 cộng script kiểm bất biến §2.5 | Quy tắc tính là trái tim của phase, phải kiểm được trước khi UI phụ thuộc vào nó |
| **CỔNG 1** | Chạy script kiểm bất biến trên dữ liệu thật. Dán kết quả | Sai quy tắc tính thì mọi thứ phía trên sai theo |
| 3 | Biểu mẫu tạo và sửa §3.1, gồm nút thêm hạng mục | |
| 4 | Trang chi tiết §3.4 và màn danh sách §3.3 | |
| **CỔNG 2** | Chủ dự án tự tạo một vấn đề có 3 hạng mục, đổi trạng thái từng cái, xem trạng thái tổng có tự đóng đúng lúc | Không test tay thì không biết quy tắc §2.1 có khớp cảm nhận thật hay không |
| 5 | Bỏ nút đóng và sửa audit §4 | Sau khi luồng mới đã chạy được |
| 6 | Dọn bộ lọc §6 | |
| 7 | Chốt: `PHASE14_RESULT.md`, gồm các giới hạn đã biết và việc còn tồn | |

Mỗi bước chạy `pytest` đầy đủ và cấp **ít nhất 20 phút** — bộ test mất khoảng 7 phút, timeout ngắn
hơn sẽ bị đọc sai thành treo.

### Điều kiện DỪNG

Dừng lại và báo, **không tự quyết**, nếu gặp:

- Đặc tả này mâu thuẫn với code thật. Đã xảy ra sáu lần trong Phase 13, và cả sáu lần việc dừng
  đều đúng.
- Phát hiện lỗ hổng bảo mật ở code cũ trong lúc làm: **ghi lại, không sửa** — đó là phạm vi audit.
- Cần thêm quyền hoặc capability mới. Xem §7.
- Việc bỏ cột `owner_user_id` gặp trở ngại ngoài dự kiến.

---

## 9. Ngoài phạm vi

Ảnh đính kèm cho hạng mục vấn đề. Bình luận hay lịch sử trao đổi trên từng hạng mục. Gán hạng mục
cho nhiều người cùng lúc. Nhắc hạn tự động qua email hay thông báo. Import Excel. Xuất báo cáo
vấn đề. Liên kết hạng mục vấn đề với phiếu tiến độ hay báo cáo ngày. Số liệu vấn đề trên dashboard
hệ thống. Duyệt hạng mục trước khi có hiệu lực.

Thay đổi kiến trúc: SPA, tự động tìm blueprint, tầng phân quyền thứ hai, đồng bộ quyền lúc khởi
động — **vĩnh viễn ngoài phạm vi**, không phải hoãn.

## 10. Cấm chạm

`app/config.py` · `pytest.ini` · `app/project_memberships.py` · `.audit/**` · bốn primitive
`project_*_required` và `can_write_project` · `app/models/audit_log.py` · bảng
`daily_report_sections` và mô đun Báo cáo ngày.

**Không** sửa bảng `report_categories` — nó dùng chung, mọi thay đổi ảnh hưởng cả Báo cáo ngày.

**Không** xoá hay sửa dữ liệu `audit_logs` đã có.

Không thêm module gate thứ năm.

## 11. Test bắt buộc

Ngoài các test chức năng thông thường:

**Quy tắc tổng hợp** — mỗi nhánh của §2.1 có một test riêng: không hạng mục nào; tất cả đóng;
có một cái đang xử lý; hỗn hợp mở và đóng. Cộng test cho `due_date` khi mọi hạng mục đều rỗng hạn,
và test `closed_date` được xoá khi mở lại một hạng mục.

**Bất biến `severity`** — sửa trạng thái hạng mục nhiều lần rồi khẳng định `issue.severity`
**không đổi**. Đây là test chặn việc ai đó "sửa cho hợp lý" bằng cách tính mức độ tổng từ hạng
mục, trái §0.1 và §2.4.

**Ràng buộc một loại một lần** — thêm hạng mục trùng loại qua HTTP → bị từ chối, và không hàng
nào được tạo. Kiểm cả ở tầng database bằng cách chèn trực tiếp và mong đợi lỗi ràng buộc.

**Phân quyền chéo dự án** — theo §7.

**Audit** — mỗi mục ở §4.2 có test riêng. Cộng một assertion phủ định: tạo hạng mục **không**
sinh hàng audit nào (theo §1.3), chụp số hàng trước và sau.

**Không còn nút đóng** — `POST` vào URL `/close` và `/reopen` cũ trả về **404**, và HTML của màn
danh sách **không** chứa hai URL đó.

**Chuyển đổi dữ liệu** — với một vấn đề cũ, sau migration có đúng một hạng mục mang đúng giá trị
cũ, và `owner_user_id` cũ đã nằm ở hạng mục.

Không dừng ở việc kiểm mã trạng thái HTTP. Khi liên quan, kiểm thêm rằng **không** có hàng database
nào, hàng audit nào, hay thay đổi nào xảy ra ở đường bị từ chối.

Nhớ rằng test chạy trên SQLite in-memory nên **không chứng minh được** hành vi PostgreSQL đồng
thời: ràng buộc UNIQUE dưới hai request cùng lúc, và `recalculate_issue_rollup` khi hai người sửa
hai hạng mục của cùng một vấn đề. Ghi giới hạn này vào `PHASE14_RESULT.md` thay vì bỏ qua im lặng.
