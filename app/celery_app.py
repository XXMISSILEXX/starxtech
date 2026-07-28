from celery import Celery
from celery.signals import worker_process_init, worker_ready
from urllib.parse import urlparse

celery_app = Celery("starx")


@worker_process_init.connect(weak=False)
def _reset_database_state_after_fork(**_kwargs):
    """Discard parent-process SQLAlchemy state in every prefork child."""
    flask_app = getattr(celery_app, "starx_flask_app", None)
    if flask_app is None:
        return
    with flask_app.app_context():
        from app.extensions import db
        db.session.remove()
        db.engine.dispose()
        flask_app.logger.info("celery.worker_process_init database pool reset")


@worker_ready.connect(weak=False)
def _log_worker_identity(**_kwargs):
    flask_app = getattr(celery_app, "starx_flask_app", None)
    if flask_app is None:
        return
    with flask_app.app_context():
        from app.extensions import db
        from sqlalchemy import text
        try:
            if db.engine.dialect.name == "postgresql":
                database, user = db.session.execute(text("SELECT current_database(), current_user")).one()
            else:
                database, user = db.engine.url.database or ":memory:", "sqlite"
            revision = db.session.execute(text("SELECT version_num FROM alembic_version")).scalar()
            from app.cli import _migration_head
            head = _migration_head()
        except Exception:
            database, user, revision, head = "unavailable", "unavailable", "unavailable", "unavailable"
        broker = urlparse(flask_app.config["CELERY_BROKER_URL"])
        flask_app.logger.info(
            "celery.worker_ready env=%s database=%s db_user=%s revision=%s head=%s storage_provider=%s "
            "bucket=%s broker_host=%s queues=%s pool=%s root=%s",
            flask_app.config["APP_ENV"], database, user, revision, head,
            flask_app.config["STORAGE_PROVIDER"], flask_app.config["STORAGE_BUCKET"],
            broker.hostname or "invalid", "media_image,media_video,storage_cleanup,bulk_download",
            "worker", flask_app.root_path,
        )

def create_celery_app(flask_app):
    celery_app.starx_flask_app = flask_app
    celery_app.conf.update(
        broker_url=flask_app.config["CELERY_BROKER_URL"],
        result_backend=flask_app.config["CELERY_RESULT_BACKEND"],
        broker_connection_retry_on_startup=True,
        task_always_eager=flask_app.config["CELERY_TASK_ALWAYS_EAGER"],
        task_eager_propagates=flask_app.config["CELERY_TASK_EAGER_PROPAGATES"],
        result_expires=flask_app.config["CELERY_RESULT_EXPIRES_SECONDS"],
        worker_prefetch_multiplier=flask_app.config["CELERY_WORKER_PREFETCH_MULTIPLIER"],
        task_acks_late=flask_app.config["CELERY_TASK_ACKS_LATE"],
        task_routes={
            "media.process_image_derivatives": {"queue": "media_image"},
            "media.process_video_derivatives": {"queue": "media_video"},
            "media.reconcile_media_jobs": {"queue": "storage_cleanup"},
            "reports.cleanup_expired_upload_sessions": {"queue": "storage_cleanup"},
            "bulk_download.build_zip": {"queue": "bulk_download"},
            "bulk_download.cleanup_expired": {"queue": "storage_cleanup"},
        },
        task_annotations={"bulk_download.build_zip": {"time_limit": flask_app.config["CELERY_TASK_TIME_LIMIT_BULK_DOWNLOAD_SECONDS"]}},
        beat_schedule={
            "cleanup-expired-report-upload-sessions": {
                "task": "reports.cleanup_expired_upload_sessions",
                "schedule": flask_app.config["REPORT_UPLOAD_CLEANUP_INTERVAL_SECONDS"],
            },
            "reconcile-media-jobs": {
                "task": "media.reconcile_media_jobs",
                "schedule": flask_app.config["MEDIA_RECONCILIATION_INTERVAL_SECONDS"],
            },
            "cleanup-expired-bulk-downloads": {
                "task": "bulk_download.cleanup_expired",
                "schedule": flask_app.config["BULK_DOWNLOAD_CLEANUP_INTERVAL_SECONDS"],
            },
        },
    )
    class ContextTask(celery_app.Task):
        abstract = True
        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                from app.extensions import db
                db.session.remove()
                try:
                    return self.run(*args, **kwargs)
                except Exception:
                    db.session.rollback()
                    raise
                finally:
                    # Worker processes are long-lived; never retain a scoped
                    # SQLAlchemy session after a task finishes or fails.
                    db.session.remove()
    celery_app.Task = ContextTask
    return celery_app
