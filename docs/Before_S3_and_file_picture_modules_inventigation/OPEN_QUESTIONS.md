# Open questions before implementation

1. Is `READONLY_ADMIN` a renamed `VIEWER_ADMIN`, an alias, or a distinct future role? Must existing users keep `VIEWER_ADMIN` code?
2. Can Project Manager view partners? If yes, which fields/companies and can they download/export contacts?
3. May Reporter edit every report in an assigned project, only reports they created, or both under separate grants?
4. May Reporter create/update/close persistent issues, and can Project Manager delete reports/issues?
5. Who may assign users to projects and alter role mappings? Is `ADMIN` allowed to manage users, reset passwords, archive projects, or only SUPER_ADMIN?
6. Should VIEWER/READONLY admin download document/photo bytes, or only view metadata/thumbnails?
7. Can Project Manager upload/download documents for assigned projects? Can they manage folders, retention or shares?
8. What are document classifications, allowed MIME types, max sizes, required metadata, retention and legal hold requirements? Is delete soft, hard, or approval-based?
9. Are event photos company-wide, department-scoped, private album, or project-associated? Who may tag people and download originals?
10. Is approval workflow required for documents/photos now or explicitly deferred? If deferred, do not prebuild it.
11. Is a public/external share ever allowed? Default recommendation: no; if later required, use revocable expiring share records, not public bucket objects.
12. Which S3-compatible provider/region, encryption/KMS, lifecycle, backup, antivirus and audit retention policy are required? Who owns credentials and incident response?
