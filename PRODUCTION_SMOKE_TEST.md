# Production Smoke Test Checklist

Run this after first deploy and after major updates.

- [ ] Open the site over HTTPS.
- [ ] Log in as `SUPER_ADMIN`.
- [ ] Create a user.
- [ ] Create a project.
- [ ] Assign a reporter to the project.
- [ ] Create a report category for the project.
- [ ] Log out and log in as the reporter.
- [ ] Create a daily report.
- [ ] Upload JPG/PNG/WEBP images to a report section.
- [ ] Open the report detail and confirm images load through `/attachments/<id>`.
- [ ] Open `/dashboard` and confirm charts/cards render.
- [ ] Open `/projects/<project_id>/dashboard`.
- [ ] Log out and log in as `VIEWER_ADMIN`.
- [ ] Confirm viewer can read dashboards/reports/issues.
- [ ] Confirm viewer cannot create, edit, delete, close, reopen, or upload.
- [ ] Run DB backup: `/opt/starx-report/scripts/backup_db.sh`.
- [ ] Run uploads backup: `/opt/starx-report/scripts/backup_uploads.sh`.
- [ ] Confirm backup files exist under `/opt/backups/starx-report`.
