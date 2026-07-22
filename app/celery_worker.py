"""Flask-aware Celery worker entrypoint.

Use ``celery -A app.celery_worker:celery_app worker ...`` so worker tasks
receive the same Flask configuration and application context as web requests.
"""
from app import create_app
from app.celery_app import celery_app

flask_app = create_app()

# Import only after create_app configured celery_app.Task as ContextTask.
import app.media_processing.tasks  # noqa: E402,F401
import app.bulk_downloads.tasks  # noqa: E402,F401
