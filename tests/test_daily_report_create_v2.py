from uuid import uuid4

from app.extensions import db
from app.models import DailyReport
from app.models import UploadSelectionSession, StorageObject
from tests.helpers.daily_report_create_v2 import DailyReportV2UploadFile, submit_daily_report_create_v2
from io import BytesIO
from PIL import Image


def _login(client):
    client.post("/login", data={"username_or_email": "reporter", "password": "password123"})


def _payload(**changes):
    data = {
        "client_request_id": str(uuid4()), "report_date": "2026-07-25",
        "overall_status": "UPDATED", "highlight": "Tiến độ trong ngày.", "summary_note": "",
        "upload_session_id": None, "attachments": [],
        "sections": [{"client_section_id": str(uuid4()), "report_category_id": 1,
                      "status": "GOOD", "content": "Đã hoàn thành hạng mục.", "sort_order": 0}],
    }
    data.update(changes)
    return data


def test_v2_finalizes_empty_report_and_retries_idempotently(client, app):
    _login(client)
    data = _payload()
    response = client.post("/api/projects/1/daily-reports/finalize", json=data)
    assert response.status_code == 200, response.get_data(as_text=True)
    report_id = response.get_json()["data"]["report_id"]
    repeated = client.post("/api/projects/1/daily-reports/finalize", json=data)
    assert repeated.status_code == 200
    assert repeated.get_json()["data"]["report_id"] == report_id
    with app.app_context(): assert DailyReport.query.count() == 1


def test_v2_duplicate_date_does_not_consume_an_upload_session(client):
    _login(client)
    first = client.post("/api/projects/1/daily-reports/finalize", json=_payload())
    assert first.status_code == 200
    second = client.post("/api/projects/1/daily-reports/finalize", json=_payload())
    assert second.status_code == 409
    assert second.get_json()["error"]["code"] == "duplicate_report_date"


def test_v2_preflight_is_read_only_and_accepts_public_category_id(client, app):
    _login(client)
    data = _payload()
    data["sections"][0]["category_id"] = data["sections"][0].pop("report_category_id")
    data["files"] = []
    response = client.post("/api/projects/1/daily-reports/preflight", json=data)
    assert response.status_code == 200, response.get_data(as_text=True)
    with app.app_context():
        assert UploadSelectionSession.query.count() == 0
        assert StorageObject.query.count() == 0
        assert DailyReport.query.count() == 0


def test_v2_preflight_duplicate_date_returns_409_without_upload_side_effect(client, app):
    _login(client)
    assert client.post("/api/projects/1/daily-reports/finalize", json=_payload()).status_code == 200
    data = _payload(); data["client_request_id"] = str(uuid4())
    data["sections"][0]["category_id"] = data["sections"][0].pop("report_category_id")
    data["files"] = []
    response = client.post("/api/projects/1/daily-reports/preflight", json=data)
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "duplicate_report_date"
    with app.app_context():
        assert UploadSelectionSession.query.count() == 0


def test_v2_requires_uuid_section_identity(client):
    _login(client)
    data = _payload()
    data["sections"][0]["client_section_id"] = "section-0"
    response = client.post("/api/projects/1/daily-reports/finalize", json=data)
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "invalid_payload"


def test_legacy_create_post_is_rejected(client):
    _login(client)
    response = client.post("/reports/projects/1/reports/create", data={})
    assert response.status_code == 405


def _jpg():
    output = BytesIO(); Image.new("RGB", (8, 8), "navy").save(output, "JPEG")
    return output.getvalue()


def test_v2_one_jpg_runs_real_upload_lifecycle(client, app):
    _login(client)
    result = submit_daily_report_create_v2(client, app, project_id=1,
        report={"report_date": "2026-07-24", "highlight": "Có ảnh"},
        sections=[{"report_category_id": 1, "content": "Ảnh tiến độ"}],
        files=[DailyReportV2UploadFile(_jpg(), "progress.jpg")])
    assert len(result["complete_responses"]) == len(result["attachment_ids"]) == 1
    assert result["storage_object_ids"]


def test_v2_maps_attachments_to_multiple_section_uuids(client, app):
    _login(client)
    result = submit_daily_report_create_v2(client, app, project_id=1,
        report={"report_date": "2026-07-22", "highlight": "Hai phần"},
        sections=[{"report_category_id": 1, "content": "Phần một"}, {"report_category_id": 2, "content": "Phần hai"}],
        files=[DailyReportV2UploadFile(_jpg(), "one.jpg", section_index=0), DailyReportV2UploadFile(_jpg(), "two.jpg", section_index=1)])
    assert len(result["attachment_ids"]) == 2
    assert len(result["section_ids"]) == 2


def test_v2_helper_rejects_more_than_three_files_per_section(client, app):
    _login(client)
    import pytest
    with pytest.raises(ValueError, match="three"):
        submit_daily_report_create_v2(client, app, project_id=1,
            report={"report_date": "2026-07-21", "highlight": "Nhiều ảnh"},
            sections=[{"report_category_id": 1, "content": "Phần"}],
            files=[DailyReportV2UploadFile(_jpg(), f"{i}.jpg") for i in range(4)])


def test_create_and_edit_load_isolated_controllers(client, app):
    _login(client)
    create = client.get("/reports/projects/1/reports/create")
    assert b"daily-report-create-v2.js" in create.data and b"report-direct-upload.js" not in create.data
    assert b"data-daily-report-create-v2" in create.data and b"data-report-direct-upload" not in create.data
    result = submit_daily_report_create_v2(client, app, project_id=1,
        report={"report_date": "2026-07-20", "highlight": "Edit contract"}, sections=[{"report_category_id": 1, "content": "Phan"}])
    edit = client.get(f"/reports/{result['report_id']}/edit")
    assert b"report-direct-upload.js" in edit.data and b"daily-report-create-v2.js" not in edit.data
    assert b"data-report-direct-upload" in edit.data and b"data-daily-report-create-v2" not in edit.data
