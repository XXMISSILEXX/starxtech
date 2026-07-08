# .env.example

Dùng nội dung này cho file `.env.example` trong source code.

```env
APP_ENV=development
FLASK_DEBUG=false
SECRET_KEY=change_me

DATABASE_URL=postgresql://starx_report:password@localhost:5432/starx_report

UPLOAD_ROOT=./storage/uploads
MAX_UPLOAD_MB=10
MAX_IMAGES_PER_SECTION=3
MAX_IMAGE_WIDTH=1920

SESSION_COOKIE_SECURE=false
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=Lax
```

Production nên sửa:

```env
APP_ENV=production
FLASK_DEBUG=false
SESSION_COOKIE_SECURE=true
```
