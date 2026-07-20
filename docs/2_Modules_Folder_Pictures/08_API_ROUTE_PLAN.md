# API Route Plan

## General rules

- All routes require login.
- POST mutations require CSRF.
- Signed URL GET does not mutate state.
- No GET mutation.
- JSON APIs return sanitized errors.
- Backend never trusts client object key, bucket, owner, status or size.
- Signed URLs are never persisted.

## Project Documents routes

### Pages

```http
GET /project-documents
GET /project-documents/projects/<project_id>
GET /project-documents/folders/<folder_id>
```

### Folder operations

```http
POST /project-documents/folders/new
POST /project-documents/folders/<id>/rename
POST /project-documents/folders/<id>/move
POST /project-documents/folders/<id>/archive
POST /project-documents/folders/<id>/restore
GET  /project-documents/folders/<id>/permissions
POST /project-documents/folders/<id>/permissions
```

### File upload/view

```http
POST /project-documents/files/presign-batch
POST /project-documents/files/complete-upload
GET  /project-documents/upload-batches/<id>
GET  /project-documents/files/<id>/signed-url
GET  /project-documents/files/<id>/derivatives/<type>/signed-url
POST /project-documents/files/<id>/archive
POST /project-documents/files/<id>/restore
```

## Company Media routes

### Pages

```http
GET /company-media
GET /company-media/albums/<album_id>
```

### Album operations

```http
POST /company-media/albums/new
POST /company-media/albums/<id>/edit
POST /company-media/albums/<id>/archive
POST /company-media/albums/<id>/restore
GET  /company-media/albums/<id>/permissions
POST /company-media/albums/<id>/permissions
```

### Media upload/view

```http
POST /company-media/files/presign-batch
POST /company-media/files/complete-upload
GET  /company-media/upload-batches/<id>
GET  /company-media/files/<id>/signed-url
GET  /company-media/files/<id>/derivatives/<type>/signed-url
POST /company-media/files/<id>/archive
POST /company-media/files/<id>/restore
```

No child album route is allowed.

## Internal/CLI only

```text
flask storage cleanup-pending --dry-run
flask storage reconcile --dry-run
flask media requeue-stuck --dry-run
```

## Authorization matrix

### Presign batch

```text
module access
+ upload permission
+ folder/album upload ACL
+ quota/limits
```

### Complete upload

```text
same as presign
+ StorageObject belongs to pending item
+ HEAD S3 verification
```

### Signed original/derivative URL

```text
module access
+ view/download permission
+ folder/album view ACL
+ active file/object
```

### Batch status

```text
batch creator
OR authorized target viewer/uploader
```
