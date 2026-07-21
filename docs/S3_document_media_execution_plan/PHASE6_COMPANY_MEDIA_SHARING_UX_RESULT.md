# Phase 6 — Company Media Sharing UX + Permission Hardening

Company Media now uses the same search-first ACL workflow as Project Documents, while retaining an ACL boundary at the album level.

## Behaviour

- The sharing screen is reached from an album and shows the breadcrumb `Thư viện media / album / Chia sẻ`.
- A picker lists only active users and existing roles. The server independently verifies that a submitted user is active and a submitted role exists.
- ACL entries are allow-only and unique per album/principal. Saving the same user or role updates its existing entry instead of adding a duplicate.
- Each entry has six independent flags: view, download, upload, edit, archive/delete, and share. Empty ACL entries are rejected.
- Presets are: **Chỉ xem**, **Xem + tải xuống**, **Cộng tác viên**, **Quản lý album**, and **Tùy chỉnh**. They fill the six flags but do not bypass normal RBAC permission codes.
- Editing an ACL locks the chosen principal until the edit is cancelled, preventing an accidental principal replacement.
- Removing an ACL is a confirmed, CSRF-protected POST. `GET ?remove_id=...` remains read-only.

## Restricted albums and inheritance

For a restricted album, a non-admin user needs both the relevant Company Media RBAC permission and a matching user or role ACL flag. ADMIN and SUPER_ADMIN keep their existing bypass behavior. For an unrestricted album, ACL rows do not restrict normal access.

All media in an album inherits that album ACL. There is no file-level ACL or per-file sharing UI.

## Manual role/user verification

1. Create or open a restricted album as an account with `company_media_albums.share`.
2. Add an active user with **Xem + tải xuống**; confirm that account can open and download only if its RBAC grants permit those actions.
3. Add a role with **Cộng tác viên** or **Quản lý album**, then test a member of that role for upload/edit or album management respectively.
4. Remove the ACL and verify the non-admin principal is denied again. A VIEWER_ADMIN cannot open or submit the sharing page.

## Explicit exclusions

This phase does not introduce file-level ACL, ZIP/bulk-download packaging, or storage namespace changes. It does not require a migration or new permission registry codes.
