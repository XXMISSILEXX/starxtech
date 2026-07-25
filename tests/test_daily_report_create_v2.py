from uuid import uuid4

from app.extensions import db
from app.models import DailyReport


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
