import json
from types import SimpleNamespace

import pytest
from celery.exceptions import Retry

from flask import has_app_context

from app.celery_app import celery_app


def test_media_tasks_are_registered_with_expected_routes(app, monkeypatch):
    from app.media_processing import tasks
    from app.bulk_downloads import tasks as bulk_download_tasks  # noqa: F401
    assert {
        "media.process_image_derivatives", "media.process_video_derivatives", "media.reconcile_media_jobs",
        "reports.cleanup_expired_upload_sessions", "bulk_download.build_zip", "bulk_download.cleanup_expired",
    } <= set(celery_app.tasks)
    assert celery_app.conf.task_routes["media.process_image_derivatives"]["queue"] == "media_image"
    assert celery_app.conf.task_routes["media.process_video_derivatives"]["queue"] == "media_video"
    assert {
        "cleanup-expired-report-upload-sessions", "reconcile-media-jobs", "cleanup-expired-bulk-downloads",
    } <= set(celery_app.conf.beat_schedule)
    def process_job_in_context(job_id):
        assert has_app_context()
        return SimpleNamespace(
            id=job_id,
            status="succeeded",
            job_type="image_derivatives" if job_id == 123 else "video_derivatives",
            storage_object_id=456,
        )

    monkeypatch.setattr("app.media_processing.pipeline.process_job", process_job_in_context)
    image_result = tasks.process_image_derivatives.apply(args=[123]).get()
    video_result = tasks.process_video_derivatives.apply(args=[124]).get()

    for result, job_id, kind in (
        (image_result, 123, "image_derivatives"),
        (video_result, 124, "video_derivatives"),
    ):
        assert result == {
            "ok": True,
            "job_id": job_id,
            "status": "succeeded",
            "kind": kind,
            "storage_object_id": 456,
        }
        assert json.loads(json.dumps(result)) == result


def test_media_task_retries_missing_job_instead_of_returning_success(app, monkeypatch):
    from app.media_processing import tasks

    monkeypatch.setattr("app.media_processing.pipeline.process_job", lambda job_id: None)

    with pytest.raises(Retry):
        tasks.process_image_derivatives.apply(args=[999]).get()


def test_reconcile_task_returns_json_safe_summary(app, monkeypatch):
    from app.media_processing import tasks

    monkeypatch.setattr(
        "app.media_processing.services.reconcile_media_jobs",
        lambda dry_run: {"matched": 2, "dry_run": dry_run},
    )

    result = tasks.reconcile_media_jobs_task.apply().get()

    assert result == {"matched": 2, "dry_run": False}
    assert json.loads(json.dumps(result)) == result
