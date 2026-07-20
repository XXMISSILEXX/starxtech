# Route and API plan

All routes require login. HTML pages render Jinja; JSON endpoints return JSON. Every state-changing POST uses Flask-WTF CSRF header/body token, including presign and complete. Signed GET endpoint returns `{url, expires_at}` (or 302 only for a simple open flow), never persists URL.

## Project Documents

| Route | Type/method | RBAC + ACL | CSRF | Response |
|---|---|---|---|---|
| `/project-documents` | page GET | module access, `projects.view` | no | project selector |
| `/project-documents/projects/<project_id>` | page GET | folder view/root + project scope | no | root browse |
| `/project-documents/folders/<id>` | page GET | folder view | no | folder browse |
| `/project-documents/folders/new` | JSON POST | folders.create + upload/create ACL parent | yes | created folder |
| `/project-documents/folders/<id>/rename` | JSON POST | folders.edit + edit ACL | yes | updated folder |
| `/project-documents/folders/<id>/move` | JSON POST | folders.edit + edit ACL source/destination | yes | updated folder |
| `/project-documents/folders/<id>/archive` / `restore` | POST | folders.delete (+ restore policy) + delete ACL | yes | redirect/JSON |
| `/project-documents/folders/<id>/permissions` | GET/POST | folders.share + share ACL | POST yes | HTML modal/JSON |
| `/project-documents/files/presign-batch` | JSON POST | files.upload + upload ACL folder | yes | per-item keys/policies |
| `/project-documents/files/complete-upload` | JSON POST | files.upload + upload ACL folder | yes | active file |
| `/project-documents/files/<id>/signed-url` | JSON GET | files.view/download + view ACL | no | short URL |
| `/project-documents/files/<id>/derivatives/<type>/signed-url` | JSON GET | files.view/download + view ACL | no | short derivative URL |
| `/project-documents/upload-batches/<id>` | JSON GET | batch creator or authorized target upload/view ACL | no | sanitized item status |
| `/project-documents/files/<id>/archive` / `restore` | POST | files.delete + delete ACL | yes | redirect/JSON |

`q`, type, status and pagination are GET query parameters. Every result is authorization-filtered before pagination; do not fetch then filter in Python.

## Company Media

| Route | Type/method | RBAC + ACL | CSRF | Response |
|---|---|---|---|---|
| `/company-media` | page GET | module + albums.view | no | album grid |
| `/company-media/albums/<id>` | page GET | albums.view + view ACL | no | media grid |
| `/company-media/albums/new` | POST | albums.create | yes | redirect/JSON |
| `/company-media/albums/<id>/edit` | POST | albums.edit + manage ACL | yes | redirect/JSON |
| `/company-media/albums/<id>/archive` / `restore` | POST | albums.delete (+ restore policy) + manage ACL | yes | redirect |
| `/company-media/albums/<id>/permissions` | GET/POST | albums.share + manage ACL | POST yes | modal/JSON |
| `/company-media/files/presign-batch` / `complete-upload` | JSON POST | files.upload + album upload ACL | yes | per-item upload state |
| `/company-media/files/<id>/signed-url` | JSON GET | files.view/download + album view ACL | no | short URL |
| `/company-media/files/<id>/derivatives/<type>/signed-url` | JSON GET | files.view/download + album view ACL | no | short derivative URL |
| `/company-media/upload-batches/<id>` | JSON GET | batch creator or authorized target upload/view ACL | no | sanitized item status |
| `/company-media/files/<id>/archive` / `restore` | POST | files.delete + album delete ACL | yes | redirect/JSON |

No route accepts child-album/folder ID for Company Media. Complete-upload rechecks RBAC/ACL before activation/enqueue. Signed URL routes never persist URL and accept no arbitrary S3 headers. No GET mutation. Cleanup/reconcile is internal Celery Beat/approved CLI only, never a public route.
