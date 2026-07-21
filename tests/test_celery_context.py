import json
from types import SimpleNamespace

from flask import has_app_context

from app.celery_app import celery_app


def test_media_tasks_are_registered_with_expected_routes(app, monkeypatch):
    from app.media_processing import tasks
    assert {"media.process_image_derivatives", "media.process_video_derivatives", "media.reconcile_media_jobs"} <= set(celery_app.tasks)
    assert celery_app.conf.task_routes["media.process_image_derivatives"]["queue"] == "media_image"
    assert celery_app.conf.task_routes["media.process_video_derivatives"]["queue"] == "media_video"
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


def test_media_task_returns_json_safe_not_found_result(app, monkeypatch):
    from app.media_processing import tasks

    monkeypatch.setattr("app.media_processing.pipeline.process_job", lambda job_id: None)

    result = tasks.process_image_derivatives.apply(args=[999]).get()

    assert result["status"] == "not_found"
    assert result["ok"] is False
    assert json.loads(json.dumps(result)) == result


def test_reconcile_task_returns_json_safe_summary(app, monkeypatch):
    from app.media_processing import tasks

    monkeypatch.setattr(
        "app.media_processing.services.reconcile_media_jobs",
        lambda dry_run: {"matched": 2, "dry_run": dry_run},
    )

    result = tasks.reconcile_media_jobs_task.apply().get()

    assert result == {"matched": 2, "dry_run": False}
    assert json.loads(json.dumps(result)) == result
