from celery import Celery

celery_app = Celery("starx")

def create_celery_app(flask_app):
    celery_app.conf.update(broker_url=flask_app.config["CELERY_BROKER_URL"], result_backend=flask_app.config["CELERY_RESULT_BACKEND"], task_always_eager=flask_app.config["CELERY_TASK_ALWAYS_EAGER"], task_eager_propagates=flask_app.config["CELERY_TASK_EAGER_PROPAGATES"], result_expires=flask_app.config["CELERY_RESULT_EXPIRES_SECONDS"], worker_prefetch_multiplier=flask_app.config["CELERY_WORKER_PREFETCH_MULTIPLIER"], task_acks_late=flask_app.config["CELERY_TASK_ACKS_LATE"], task_routes={"media.process_image_derivatives": {"queue":"media_image"}, "media.process_video_derivatives": {"queue":"media_video"}, "media.reconcile_media_jobs": {"queue":"storage_cleanup"}, "bulk_download.build_zip": {"queue":"bulk_download"}, "bulk_download.cleanup_expired": {"queue":"storage_cleanup"}}, task_annotations={"bulk_download.build_zip": {"time_limit": flask_app.config["CELERY_TASK_TIME_LIMIT_BULK_DOWNLOAD_SECONDS"]}})
    class ContextTask(celery_app.Task):
        abstract = True
        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                try:
                    return self.run(*args, **kwargs)
                finally:
                    # Worker processes are long-lived; never retain a scoped
                    # SQLAlchemy session after a task finishes or fails.
                    from app.extensions import db
                    db.session.remove()
    celery_app.Task = ContextTask
    return celery_app
