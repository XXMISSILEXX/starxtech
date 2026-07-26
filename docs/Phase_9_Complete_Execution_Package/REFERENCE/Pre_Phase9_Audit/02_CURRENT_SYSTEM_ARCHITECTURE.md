# Current system architecture

**VERIFIED** from `app/__init__.py::create_app/register_blueprints`, `app/celery_app.py`, `app/storage/`, and `app/media_processing/`.

```mermaid
flowchart LR
 Browser[Jinja + Bootstrap + Chart.js + V2 JS] --> Flask[Flask blueprints]
 Flask --> PG[(PostgreSQL / SQLAlchemy)]
 Flask --> S3[S3/MinIO private objects]
 Flask --> Redis[Redis broker/result backend]
 Redis --> Celery[Celery media workers]
 Celery --> S3
 Celery --> PG
```

Blueprints: auth/account, modules/navigation, dashboard/API, projects, reports and `daily_report_create_v2`, issues, attachments, admin, and independent partner/document/media modules. `create_app` installs global login and Reports-module guards; all non-public endpoints require login. Background jobs are staged on V2 finalize then dispatched after DB commit (`app/reports/services.py::finalize_daily_report_create_v2`).

**INFERRED.** Phase 9 should remain a Reports-domain extension: reuse its services and tables without coupling Partner module models.
