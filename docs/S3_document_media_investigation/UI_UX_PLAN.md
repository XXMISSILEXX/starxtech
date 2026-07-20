# UI/UX plan

## Project Documents

Use a project selector (or project sidebar on wide screens), then a folder page with breadcrumb, search, type/status filters, grid/list toggle and create/upload/share controls conditionally rendered from effective permission. Folder cards show name, direct child counts, image collage only from permitted active thumbnail records; list shows uploader/date/type/size. Do not show inaccessible folder names/counts in search or breadcrumb.

Grid file cards show image thumbnail; image click requests signed inline URL then opens lightbox. Video card requests signed URL only on play; use client-generated thumbnail or placeholder. Documents/audio use MIME icons and open/download action. Large multi-image folder may show a bounded collage (for example first four thumbnails), never presign every object just to render a list—prefer thumbnail signing lazy/on visible cards or a controlled short batch endpoint.

Create/rename/move/share are Bootstrap modals with server errors visible. Move destination picker excludes current node/descendants. View-only users see browse/download controls only. Empty state explains no active content; denied state is generic “Bạn không có quyền truy cập” and must not disclose existence.

Add drag/drop zone and multiple-file picker. An upload queue shows per-file progress, accepted/rejected state, retry/cancel and partial success; processing images/videos show placeholder until worker derivatives are ready, then the grid refreshes through batch-status polling. On mobile the drop zone becomes a full-width picker, queue cards stack with an accessible progress label and one action row; do not create a long signed URL list for every album object.

## Company Media

Landing page is album card grid with cover thumbnail, title, event date, media count and archived badge. Search title/date/status; no “new folder” inside album. Inside, responsive image/video grid and lightbox/gallery controls; lazy-load signed URLs only when thumbnail/view is needed. Album editor supplies name, date, description and selected cover; share modal is available only with album share/manage permission.

## Mobile and accessibility

One-column cards below Bootstrap `md`, touch targets at least 44px, button labels plus icons, keyboard-operable modal/lightbox, Escape close, focus trap/return focus, descriptive alt from filename/caption, video controls/captions future. Do not put signed URLs in page HTML/data attributes longer than needed. UI is convenience only: hidden controls never replace backend authorization.
