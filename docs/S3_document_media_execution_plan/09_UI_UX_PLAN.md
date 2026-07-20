# UI/UX Plan

## Project Documents UI

### Main layout

- Project selector or project sidebar.
- Breadcrumb folder path.
- Search box.
- Type filter:
  - Tất cả
  - Tài liệu
  - Ảnh
  - Video
  - Âm thanh
- Status filter:
  - Đang hoạt động
  - Đã lưu trữ
  - Tất cả
- Grid/list toggle.
- Create folder button.
- Upload button/drag zone.
- Share/manage permissions button when allowed.

### Folder cards

- Folder icon.
- Name.
- Direct child count if user has permission.
- Optional image collage from permitted thumbnails.
- No inaccessible names/counts.

### File cards

- Image: thumbnail.
- Video: poster/placeholder.
- Document/audio: MIME icon.
- File name, size, uploaded by/date.
- Processing status badge.
- Actions:
  - Xem/Mở.
  - Tải xuống.
  - Lưu trữ.
  - Khôi phục.
  - Sửa metadata.

### Drag/drop queue

- Full-width upload zone.
- Multiple file picker.
- Queue panel with per-file:
  - filename
  - type
  - size
  - progress
  - status
  - retry/cancel
- Partial success messaging.
- Poll batch status.

### Lightbox

- Image click -> request preview signed URL.
- Next/prev navigation within authorized result set.
- Button “Tải ảnh gốc”.
- Video click -> request original signed URL and play.
- Do not pre-sign all originals on page load.

## Company Media UI

### Album grid

- Album cover.
- Title.
- Event date.
- Description preview.
- Media count.
- Archived badge.
- Share/manage buttons if allowed.

### Inside album

- No create subfolder button.
- Drag/drop image/video.
- Responsive grid.
- Lightbox/gallery.
- Video poster.
- Upload progress queue.
- Cover selection.
- Search/filter.

## Mobile

- One-column cards below Bootstrap `md`.
- Drop zone becomes full-width file picker.
- Queue items become stacked cards.
- Touch targets >= 44px.
- Buttons have icon + text or accessible labels.
- Lightbox keyboard/touch accessible.
- Focus trap in modals.
- Escape closes modal/lightbox.
- Generic denied state:
  - “Bạn không có quyền truy cập”
  - do not reveal existence.
