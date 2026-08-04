# Phase 13 — Audit log: chính sách ghi và trang xem

Đọc `CLAUDE.md` trước. Phase trước: `docs/Phase12_Progress_Construction_And_Beyond/PHASE12_RESULT.md`.

Trạng thái: **chưa triển khai**. Nguồn yêu cầu: chủ dự án, sau khi Phase 12 bật xoá cứng
ba cấp trong mô đun tiến độ và phát hiện không ai ngoài người truy cập được SQL đọc được
audit log.

---

## 0. Hiện trạng — số liệu thật, không phải phỏng đoán

Đo trên PostgreSQL development ngày 2026-08-04:

| Chỉ số | Giá trị |
|---|---|
| Số bản ghi | 1235 |
| Kích thước bảng | 632 kB, tức khoảng **512 byte một hàng** |
| Số action khác nhau | **76** |
| Index | **chỉ có khoá chính** — không index nào trên `created_at`, `action`, `actor_user_id`, `entity_type` |
| Mô đun đang ghi | 14, qua một điểm vào duy nhất |

Điểm vào: `app/audit.py:9` `log_audit(action, entity_type, entity_id, old_values, new_values)`,
với alias `audit = log_audit` ở dòng 49. Một số mô đun import `log_audit`, số khác import
`audit` — **cùng một hàm**. Nhờ vậy mọi thay đổi chính sách chỉ cần đặt tại một chỗ.

Cột của `audit_logs`: `id`, `actor_user_id`, `action`, `entity_type`, `entity_id`,
`old_values_json`, `new_values_json`, `ip_address`, `user_agent`, `created_at`.
**Không có `project_id`.**

### Ba vấn đề đã xác minh

1. **Snapshot khi xoá viết thiếu.** Bản ghi `attachment.delete` thật trong database chỉ
   chứa `{"daily_report_section_id": 9}` — không tên file, không ai đã upload, không thời
   điểm, không kích thước. Xoá một ảnh khỏi báo cáo và audit log nói được đúng một điều:
   nó thuộc section số 9.

2. **Company media không ghi xoá file.** Danh sách action của mô đun chỉ có cấp album
   (`archive`, `restore`, `share`, `revoke`, `cover`, `rename`, `create`) và
   `company_media.file.create`. Không có action nào cho việc xoá một file. Phải xác minh:
   hoặc file không xoá lẻ được, hoặc xoá mà không ghi gì — trường hợp thứ hai là lỗ hổng
   lớn hơn mọi thứ khác trong tài liệu này.

3. **Tín hiệu bị chôn.** `company_media.file.create` chiếm **480 trong 1235 bản ghi
   (39%)**, còn `construction_progress.group.delete` — thứ duy nhất không hoàn tác được —
   chỉ có **3**.

Con số làm rõ thứ tự ưu tiên: `attachment.create` có **139** bản ghi,
`attachment.delete` có **3**. Muốn trả lời "ai upload file vừa bị xoá", sửa 3 bản ghi xoá
cho đủ nội dung rẻ hơn giữ 139 bản ghi tạo **46 lần**.

---

## 1. Quyết định đã chốt

1. **Ghi một hành động khi audit là cách duy nhất để biết nó đã xảy ra.** Bản ghi còn tồn
   tại thì `created_by` và `created_at` trên chính hàng đó đã trả lời.

2. **Không ghi `*.create` của nội dung.** Bỏ khoảng **68% khối lượng hiện tại mà không mất
   thông tin nào**.

3. **Vẫn ghi `*.create` của thẩm quyền** — `user.create`, `role.create`. Ranh giới là
   **nội dung so với thẩm quyền**, không phải tạo so với xoá. Tạo một tài khoản là hành
   động nhạy cảm; tạo một file ảnh thì không.

4. **Ghi tải file gốc và tải hàng loạt.** Đây là nhóm tần suất cao duy nhất mà audit là
   bản ghi duy nhất — không chỗ nào khác ghi ai đã lấy dữ liệu ra khỏi hệ thống. Chỉ ghi
   file gốc, **không** ghi xem preview hay thumbnail.

5. **Không thêm module gate thứ năm.** Blueprint riêng `app/audit_log/`, nhóm dưới khu vực
   quản trị trong `get_active_module()` — đúng tiền lệ `admin_storage`, không đổi kiến trúc.

6. **Không lọc theo dự án** ở phiên bản này, vì `audit_logs` không có `project_id` và suy
   từ `entity_type`/`entity_id` đa hình sẽ vừa chậm vừa sai.

7. **Retention viết thành tài liệu ngay, logic làm sau.** Lý do: "làm sau" mà không viết
   ra thì thành "không bao giờ", và khi đó nó là vấn đề của bảng nửa triệu hàng.

---

## 2. Bảng ánh xạ `action → nhóm`

Đặt trong `app/audit.py`, cạnh `log_audit`. **Một nguồn duy nhất** cho cả trang xem và
logic retention sau này. Mặc định khi action chưa được khai là **`retain_forever`** — fail
safe theo hướng giữ, không theo hướng xoá.

```
AUDIT_GROUP_DESTRUCTIVE = "destructive"   # xoá, lưu trữ, khôi phục, vô hiệu hoá
AUDIT_GROUP_AUTHORITY   = "authority"     # quyền, vai, thành viên, chia sẻ
AUDIT_GROUP_MUTATION    = "mutation"      # sửa hồ sơ, giá trị cũ mất luôn
AUDIT_GROUP_SECURITY    = "security"      # đăng nhập thất bại, lệnh CLI
AUDIT_GROUP_DISCLOSURE  = "disclosure"    # tải file, tải hàng loạt
```

Bốn nhóm đầu **giữ vĩnh viễn**. `disclosure` giữ **24 tháng**.

### Nhóm `destructive`

Mọi action kết thúc bằng `.delete`, `.archive`, `.restore`, `.deactivate`. Hiện có:
`attachment.delete` · `report.delete` · `project_update.delete` ·
`construction_progress.entry.delete` · `construction_progress.group.delete` ·
`construction_progress.item.delete` · `construction_progress.type.delete` ·
`construction_progress.group.archive` · `construction_progress.type.archive` ·
`document.file.archive` · `document.file.restore` · `document.folder.archive` ·
`document.folder.restore` · `company_media.album.archive` · `company_media.album.restore` ·
`company.archive` · `company.restore` · `customer.archive` · `project.archive` ·
`partner.archive` · `partner.restore` · `partner.deactivate`

Khôi phục nằm cùng nhóm với lưu trữ: cần biết ai đã khôi phục, không chỉ ai đã ẩn.

### Nhóm `authority`

`role.create` · `role.permissions.update` · `user.create` · `user.update` ·
`user.reset_password` · `user.seed_admin` · `user.seed_admin.update` ·
`project_membership.assign` · `project_membership.update` · `project_membership.deactivate` ·
`project_user.assign` · `project_user.remove` · `document.folder.share` ·
`document.folder.revoke` · `company_media.album.share` · `company_media.album.revoke`

Chia sẻ và thu hồi nằm ở đây, **không** ở `disclosure`, vì chúng đổi **ai được xem** chứ
không phải ghi nhận một lượt xem.

### Nhóm `mutation`

`report.update` · `project_update.update` · `construction_progress.entry.update` ·
`construction_progress.item.update` · `construction_progress.group.update` ·
`construction_progress.type.update` · `customer.update` · `project.update` ·
`project.customer.move` · `partner.update` · `partner_company.update` ·
`partner_department.update` · `document.file.rename` · `document.folder.rename` ·
`document.folder.move` · `company_media.album.rename` ·
`project_contractor_assignment.end`

### Nhóm `security`

`auth.login_failed` và mọi action sinh từ `app/cli.py`.

### Nhóm `disclosure`

`document.file.download`, cộng ba action **phải thêm mới** ở mục 4.

### Bỏ khỏi audit hoàn toàn

`company_media.file.create` · `attachment.create` · `document.file.create` ·
`report.create` · `construction_progress.item.create` ·
`construction_progress.group.create` · `construction_progress.entry.create` ·
`construction_progress.type.create` · `category.create` · `document.folder.create` ·
`document.custom_root.create` · `company_media.album.create` · `project_update.create` ·
`partner.create` · `partner_company.create` · `partner_department.create` ·
`partner_field_collection.create` · `customer.create` · `project.create` ·
`project_contractor.create` · `project_contractor_assignment.create` · `issue.create` ·
`company_media.album.cover` · `account.ui_preferences.updated`

Bỏ nghĩa là **xoá lời gọi `log_audit`/`audit` ở chỗ tạo**, không phải xoá dữ liệu cũ. Dữ
liệu đã ghi giữ nguyên; bộ lọc mặc định của trang xem che chúng.

---

## 3. Ưu tiên một — sửa snapshot khi xoá

Trang xem chỉ hiển thị được những gì đã ghi. `{"daily_report_section_id": 9}` thì hiển thị
đẹp cũng không trả lời được gì. **Làm việc này trước khi làm trang xem.**

Quy tắc nội dung `old_values` cho mọi action nhóm `destructive`:

| Loại đối tượng | Phải chụp |
|---|---|
| File (đính kèm, tài liệu, media) | tên file, người tạo, thời điểm tạo, kích thước, mã object storage, và đối tượng cha |
| Bản ghi nghiệp vụ (báo cáo, phiếu, vấn đề) | các trường nội dung chính, người tạo, thời điểm tạo |
| Cấu trúc có con (khu vực, loại tiến độ, thư mục, album) | tên của chính nó, cộng số lượng và nội dung tóm tắt của các con bị xoá theo |

Mô đun tiến độ đã làm đúng việc này ở Phase 12.1 — dùng nó làm khuôn. Xem
`construction_progress.group.delete` trong dữ liệu dev: nó chụp `counts`, danh sách khu
vực, hạng mục, và từng phiếu kèm `report_date`, `quantity`, `note`, `created_by`.

Với action nhóm `mutation`: chỉ ghi **trường đã đổi**, không ghi cả đối tượng. Hàng nhỏ
hơn và người đọc thấy ngay cái gì thay đổi.

Không lưu thứ join được: đã có `actor_user_id` thì không lưu thêm tên và email của người
thực hiện, vì chúng sẽ lỗi thời.

---

## 4. Bổ sung ghi tải file

Ba action mới, nhóm `disclosure`:

| Action | Khi nào ghi | Nội dung |
|---|---|---|
| `company_media.file.download` | tải **file gốc** từ thư viện media | tên file, mã album |
| `attachment.download` | tải **file gốc** đính kèm báo cáo | tên file, mã báo cáo và section |
| `bulk_download.create` | mỗi **lượt** tải hàng loạt | số lượng file, tổng dung lượng, loại đối tượng, danh sách tóm tắt |

**Tải hàng loạt ghi một bản ghi cho cả lượt**, không phải mỗi file một bản ghi. Tải 500
file mà ghi 500 hàng nghĩa là 500 lệnh insert cộng cập nhật index bên trong request —
người dùng thấy chậm và bảng phình vì một hành động.

**Chỉ ghi khi phục vụ file gốc.** Xem preview và thumbnail không ghi. Hệ thống đã tách rõ
hai đường này theo quy tắc trong `CLAUDE.md`; ghi đúng đường thứ hai.

Bổ sung nhóm `destructive` và `mutation` cho `issues`: hiện chỉ có `issue.create` và
`issue.update`, thiếu xoá và đóng/mở lại. Thêm `issue.delete`, `issue.close`,
`issue.reopen`.

**Trước khi làm mục này**, xác minh vấn đề 2 ở mục 0: file company media có xoá lẻ được
không, và nếu có thì hiện có ghi audit không. Nếu chưa ghi thì thêm
`company_media.file.delete` vào nhóm `destructive` với snapshot đầy đủ — việc đó **quan
trọng hơn** ghi lượt tải.

---

## 5. Index và tính chỉ-ghi-thêm

Bốn index, thêm bằng một migration:

| Index | Phục vụ |
|---|---|
| `created_at DESC` | sắp xếp mặc định và lọc khoảng thời gian |
| `(action, created_at DESC)` | bộ lọc theo nhóm kết hợp sắp xếp |
| `(actor_user_id, created_at DESC)` | lọc theo người thực hiện |
| `(entity_type, entity_id)` | câu hỏi điều tra thật: "chuyện gì đã xảy ra với khu vực số 5" |

Làm ngay vì bảng đang 1235 hàng nên thêm là tức thời. Ở nửa triệu hàng thì cần
`CREATE INDEX CONCURRENTLY` và phải cẩn thận ngoài transaction.

**Chỉ ghi thêm**: không có code ứng dụng nào được UPDATE hay DELETE trên `audit_logs`. Job
retention sau này là thứ duy nhất được xoá, và nó tự ghi một bản ghi audit nói đã xoá bao
nhiêu hàng của khoảng nào.

---

## 6. Trang xem

Blueprint `app/audit_log/`, đăng ký tay trong `register_blueprints()`. Nhóm dưới khu vực
quản trị trong `get_active_module()` — đúng cách `admin_storage` đang làm.

### Phân quyền

- Permission code mới. Kiểm `_RESOURCES` trong `app/permissions/registry.py` xem có
  resource phù hợp chưa (`security`, `system`); ưu tiên dùng lại, nếu không thì thêm
  resource `audit_logs` với code `audit_logs.view`.
- Thêm vào `DEFAULTS` cho `ADMIN` và `VIEWER_ADMIN` — trang chỉ đọc nên vai chỉ-xem hợp lý.
- **Không** thêm capability theo dự án; đây là trang hệ thống.
- **Module gate**: tuple `report_endpoints` trong `require_reports_module_access`
  (`app/__init__.py`) **không** chứa tiền tố `"admin."` — nó liệt kê một số endpoint admin
  cụ thể. Trang audit là trang quản trị hệ thống nên **không** đòi quyền phân hệ Quản lý
  dự án. **Xác nhận lại bằng cách đọc code** rồi ghi kết luận vào báo cáo.
- Liên kết điều hướng **không** hiện với người thiếu quyền.

### Danh sách

Cột: thời điểm, người thực hiện, hành động, nhóm, loại đối tượng, mã đối tượng, địa chỉ IP.
Mới nhất trước.

- Phân trang LIMIT/OFFSET ở tầng SQL cộng một câu COUNT riêng. **Không** `.all()` rồi cắt
  trong Python.
- Nạp sẵn `actor_user` để tránh N+1.
- Bộ lọc: **nhóm** (mặc định là bốn nhóm quan trọng, tức loại `disclosure` khỏi khung nhìn
  đầu tiên), khoảng thời gian, action, `entity_type`, người thực hiện. Tất cả nằm trong URL
  để chia sẻ được và bấm Back đúng.
- Dropdown `action` và `entity_type` sinh từ giá trị thực có trong bảng, không hardcode.
- Trạng thái rỗng và trạng thái "bộ lọc không khớp" là hai thông báo khác nhau.
- Không dùng giá trị tham số để dựng tên template hay tên thuộc tính.

### Chi tiết một bản ghi

`old_values` và `new_values` cạnh nhau, dạng bảng khoá–giá trị dễ đọc, **không** phải JSON
thô. Kèm `user_agent` đầy đủ.

Hai cột JSON có thể là **object, JSON `null`, hoặc SQL NULL** — dev hiện có 999 hàng
`old_values_json` là JSON `null`. Template phải xử lý cả ba mà không nổ lỗi.

### Chỉ đọc tuyệt đối

Không route sửa, xoá, tạo. Không nút nào dẫn tới mutation. Một audit log sửa được thì
không còn là audit log.

### Che trường nhạy cảm

Che giá trị của mọi khoá khớp danh sách chặn: `password`, `pass`, `token`, `secret`,
`hash`, `key`, `credential`, `signature`, `api_key`, `access_token`, `refresh_token`.
So khớp **không phân biệt hoa thường** và trên **khoá lồng**, không chỉ cấp một. Giá trị bị
che hiện `••• đã che •••`, giữ nguyên tên khoá để người đọc biết trường đó tồn tại.

**Danh sách cho phép, ưu tiên cao hơn danh sách chặn.** Một số khoá hợp lệ chứa chuỗi nằm
trong danh sách chặn và **không được che**:

| Khoá | Vì sao không che |
|---|---|
| `object_key` | Đường dẫn object trong bucket. Đây là trường dùng để tìm lại và khôi phục file bị xoá — che nó là làm snapshot vô dụng. Biết object key không cấp quyền truy cập; truy cập cần presigned URL hoặc credential |
| `storage_object_id` | Chỉ là khoá ngoại số |

Cách làm: kiểm danh sách cho phép **trước**, nếu khớp thì giữ nguyên; chỉ khi không khớp mới
xét danh sách chặn. Khi thêm khoá mới vào snapshot, người thêm phải kiểm nó có bị danh sách
chặn bắt oan không.

Phát hiện này đến từ snapshot thật của `company_media.file.delete` ở Bước 2a: nó chứa
`object_key`, và quy tắc so khớp chứa-chuỗi ban đầu sẽ che chính trường quan trọng nhất.

Test bắt buộc: một snapshot chứa cả `object_key` và `password_hash` → `object_key` **hiện
nguyên**, `password_hash` **bị che**.

Dữ liệu hiện sạch — đã kiểm 892 bản ghi có JSON dạng object, không khoá nào khớp danh sách
trên. Đây là bảo hiểm cho lời gọi `log_audit` sau này.

---

## 7. Retention — viết tài liệu, chưa làm logic

| Nhóm | Giữ |
|---|---|
| `destructive`, `authority`, `mutation`, `security` | **Vĩnh viễn** |
| `disclosure` | **24 tháng** rồi xoá |

24 tháng cho nhóm tải file vì một tranh chấp về hồ sơ thường nổ ra trong vòng một đến hai
năm, sau đó giá trị điều tra gần như bằng không.

Khi làm logic sau này: job phải idempotent, xoá theo lô để không lock bảng, và **tự ghi
một bản ghi audit** nhóm `security` nói đã xoá bao nhiêu hàng của khoảng thời gian nào.

Phase này **không** viết logic đó. Chỉ ghi bảng trên vào tài liệu.

---

## 8. Kế hoạch thi hành

Bảy bước, mỗi bước một commit, mỗi commit `pytest` xanh toàn bộ.
**Ngân sách pytest ít nhất 20 phút** — suite khoảng 6 phút, 624 test.

| Bước | Nội dung | Lý do xếp ở đây |
|---|---|---|
| 0 | Mốc xanh, ghi `BASELINE_13.md` | Không có mốc thì test đỏ sau này không quy được trách nhiệm |
| 1 | Xác minh vấn đề 2 mục 0: file media có xoá lẻ mà không ghi audit không. Báo cáo kết quả, chưa sửa gì | Nếu có lỗ hổng thì nó đổi thứ tự các bước sau |
| 2 | Sửa snapshot khi xoá cho mọi action `destructive` | Trang xem chỉ hiện được những gì đã ghi |
| 3 | Bảng ánh xạ `action → nhóm` trong `app/audit.py`, và bỏ các lời gọi audit ở chỗ tạo nội dung | Một nguồn duy nhất cho trang xem và retention |
| 4 | Bốn index, một migration | Rẻ bây giờ, đắt ở nửa triệu hàng |
| 5 | Ba action tải file mới, cộng `issue.delete/close/reopen` | Sau khi chính sách đã rõ |
| 6 | Blueprint `app/audit_log/`, hai màn hình, permission code, che trường nhạy cảm | Bề mặt mới, cần đủ phân quyền |
| 7 | Chốt: `PHASE13_RESULT.md`, gồm đoạn retention ở mục 7 | |

Cổng dừng: sau **Bước 1** (kết quả xác minh có thể đổi kế hoạch), sau **Bước 2** (để chủ dự
án xoá thử một thứ và xem snapshot đã đủ chưa), và sau **Bước 6** (xem trang thật).

### File được phép sửa

```
app/audit.py                                  bảng ánh xạ nhóm
app/audit_log/{__init__,routes}.py            blueprint mới
app/templates/audit_log/*.html                hai màn hình
app/__init__.py                               register_blueprints
app/navigation.py                             nhóm dưới khu vực quản trị
app/permissions/registry.py                   permission code + DEFAULTS
app/attachments/**, app/company_media/**, app/project_documents/**,
app/reports/**, app/issues/**, app/bulk_downloads/**,
app/construction_progress/**, app/partners/**, app/partner_*/**,
app/customers/**, app/project_operations/**, app/admin/**, app/account/**
                                              sửa snapshot xoá, bỏ audit ở chỗ tạo, thêm audit tải file
migrations/versions/<hash>_*.py               một migration cho bốn index
tests/**                                      test mới và cập nhật test cũ
docs/Phase13_Audit_Log/**
```

Cấm chạm: `app/config.py`, `pytest.ini`, `app/auth/permissions.py`,
`app/project_memberships.py`, `.audit/**`, bốn primitive
`project_read_required`/`project_write_required`/`project_manage_required`/`can_write_project`,
và **không thêm module gate thứ năm**.

Không xoá hay sửa dữ liệu audit đã có. Không đổi chữ ký của `log_audit`.

### Kiểm thử bắt buộc

**Bảng ánh xạ**: mọi action trong danh sách mục 2 trả về đúng nhóm; action lạ trả về
`retain_forever`; mọi action đang tồn tại trong dữ liệu dev đều có nhóm hoặc rơi vào mặc
định an toàn.

**Snapshot xoá**: với mỗi loại đối tượng ở mục 3, xoá một bản ghi rồi khẳng định
`old_values` chứa đủ các trường bắt buộc. Đặc biệt `attachment.delete` phải chứa tên file
và người tạo — hiện chỉ có `daily_report_section_id`.

**Bỏ audit ở chỗ tạo**: sau khi tạo một file, một báo cáo, một hạng mục, khẳng định
**không** có bản ghi audit mới nào. Assertion phủ định, viết cho đúng.

**Tải file**: tải file gốc sinh một bản ghi; xem preview và thumbnail **không** sinh bản
ghi nào; tải hàng loạt 3 file sinh **đúng một** bản ghi kèm số lượng 3.

**Trang xem**: ma trận 7 vai; liên kết điều hướng ẩn khi thiếu quyền; phân trang; từng bộ
lọc; bộ lọc mặc định **không** hiện nhóm `disclosure` nhưng **có** hiện nhóm `destructive`;
che trường nhạy cảm gồm khoá lồng; ba dạng JSON (object, JSON null, SQL NULL) render không
lỗi; không tồn tại route mutation nào.

**Index**: migration `upgrade` và `downgrade` chạy được; xác nhận bốn index tồn tại sau
`upgrade`.

Chốt: `grep -rnF '\x' tests/` cho các file test mới phải rỗng. Assertion tiếng Việt dùng
`response.get_data(as_text=True)`.

Deploy cần `flask db upgrade` (bốn index) **và** `flask sync-permissions --apply-defaults`
(permission code mới). Ghi rõ vào báo cáo, và chạy cả hai trên database development sau khi
commit để chủ dự án xem được trang.

---

## 9. Ngoài phạm vi

Logic retention (chỉ viết tài liệu ở mục 7). Lọc theo dự án (bảng không có `project_id`).
Xuất audit log ra file. Cảnh báo tự động khi có hành động nguy hiểm. Ghi lại lượt xem
preview và thumbnail. Ghi lại `*.create` của nội dung — đã quyết định bỏ ở mục 1.
