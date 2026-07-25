"""Canonical integration helper for the Daily Report Create V2 API."""
from dataclasses import dataclass
from uuid import uuid4

from flask import url_for
from sqlalchemy import select

from app.extensions import db
from app.models import (DailyReport, DailyReportSection, MediaProcessingJob,
                        ReportAttachment, StorageObject, UploadSelectionSession)


@dataclass
class DailyReportV2UploadFile:
    content: bytes
    filename: str
    mime_type: str = "image/jpeg"
    section_index: int = 0


def assert_v2_finalize_response(response):
    assert response.content_type.startswith("application/json")
    assert response.status_code in {200, 201}, response.get_data(as_text=True)
    payload = response.get_json()
    assert payload["ok"] is True
    data = payload["data"]
    assert isinstance(data["report_id"], int)
    assert data["redirect_url"].endswith(f"/reports/{data['report_id']}")
    return data


def submit_daily_report_create_v2(client, app, *, project_id, report, sections,
                                  files=None, client_request_id=None):
    """Exercise the real V2 preflight, upload, complete, and finalize lifecycle."""
    files = list(files or [])
    section_ids = [str(uuid4()) for _ in sections]
    if any(file.section_index < 0 or file.section_index >= len(sections) for file in files):
        raise ValueError("section_index must refer to a supplied section")
    if any(sum(file.section_index == index for file in files) > 3 for index in range(len(sections))):
        raise ValueError("at most three files are allowed per section")
    client_file_ids = [str(uuid4()) for _ in files]
    if len(set(client_file_ids)) != len(client_file_ids):
        raise AssertionError("client_file_id must be unique")
    with app.test_request_context():
        preflight_url = url_for("daily_report_create_v2.preflight", project_id=project_id)
        session_url = url_for("daily_report_create_v2.create_session", project_id=project_id)
        finalize_url = url_for("daily_report_create_v2.finalize", project_id=project_id)
    normalized_sections = [
        {"client_section_id": section_ids[index], "category_id": section["report_category_id"],
         "report_category_id": section["report_category_id"], "status": section.get("status", "INFO"),
         "content": section["content"], "sort_order": section.get("sort_order", index)}
        for index, section in enumerate(sections)
    ]
    preflight_response = client.post(preflight_url, json={
        "client_request_id": client_request_id or str(uuid4()), "report_date": report["report_date"],
        "overall_status": report.get("overall_status", "UPDATED"), "highlight": report["highlight"],
        "summary_note": report.get("summary_note", ""), "sections": normalized_sections,
        "files": [{"client_file_id": file_id, "client_section_id": section_ids[file.section_index],
                   "filename": file.filename, "mime_type": file.mime_type, "size": len(file.content), "sort_order": index}
                  for index, (file_id, file) in enumerate(zip(client_file_ids, files))],
    })
    assert preflight_response.status_code == 200, preflight_response.get_data(as_text=True)
    session_response = None
    presign_responses, complete_responses, items = [], [], []
    session_id = None
    if files:
        session_response = client.post(session_url, json={"file_count": len(files), "total_size_bytes": sum(len(file.content) for file in files)})
        assert session_response.status_code == 200, session_response.get_data(as_text=True)
        session_id = session_response.get_json()["data"]["upload_session_id"]
        with app.test_request_context():
            presign_url = url_for("daily_report_create_v2.presign", project_id=project_id, session_id=session_id)
        presign = client.post(presign_url, json={"files": [
            {"client_file_id": file_id, "client_section_id": section_ids[file.section_index],
             "filename": file.filename, "mime_type": file.mime_type, "size": len(file.content)}
            for file_id, file in zip(client_file_ids, files)
        ]})
        assert presign.status_code == 200, presign.get_data(as_text=True)
        presign_responses.append(presign)
        items = presign.get_json()["data"]["items"]
        by_client = {item["client_file_id"]: item for item in items}
        assert set(by_client) == set(client_file_ids)
        provider = app.extensions["storage_provider"]
        for file_id, file in zip(client_file_ids, files):
            item = by_client[file_id]
            with app.app_context():
                storage = db.session.get(StorageObject, item["storage_object_id"])
                provider.put_bytes(storage.bucket, storage.object_key, file.content, storage.mime_type)
            with app.test_request_context():
                complete_url = url_for("daily_report_create_v2.complete", project_id=project_id, session_id=session_id, item_id=item["upload_batch_item_id"])
            complete = client.post(complete_url, json={})
            assert complete.status_code == 200, complete.get_data(as_text=True)
            complete_responses.append(complete)
    attachments = [
        {"upload_item_id": item["upload_batch_item_id"], "client_section_id": section_ids[file.section_index], "sort_order": index}
        for index, (item, file) in enumerate(zip(items, files))
    ]
    finalize_response = client.post(finalize_url, json={
        "client_request_id": client_request_id or str(uuid4()), "report_date": report["report_date"],
        "overall_status": report.get("overall_status", "UPDATED"), "highlight": report["highlight"],
        "summary_note": report.get("summary_note", ""), "upload_session_id": session_id,
        "sections": normalized_sections, "attachments": attachments,
    })
    data = assert_v2_finalize_response(finalize_response)
    with app.app_context():
        report_id = data["report_id"]
        report_row = db.session.get(DailyReport, report_id)
        upload_session = db.session.get(UploadSelectionSession, session_id) if session_id else None
        section_rows = db.session.scalars(select(DailyReportSection).where(DailyReportSection.daily_report_id == report_id)).all()
        attachment_rows = db.session.scalars(select(ReportAttachment).join(DailyReportSection).where(DailyReportSection.daily_report_id == report_id)).all()
        storage_ids = [row.storage_object_id for row in attachment_rows]
        media_job_ids = [row.id for row in db.session.scalars(select(MediaProcessingJob).where(MediaProcessingJob.storage_object_id.in_(storage_ids or [-1]))).all()]
        storage_rows = [db.session.get(StorageObject, storage_id) for storage_id in storage_ids]
        for row in [report_row, upload_session, *section_rows, *attachment_rows, *storage_rows]:
            if row is not None:
                db.session.expunge(row)
    return {"preflight_response": preflight_response, "upload_session_response": session_response,
            "session_response": session_response, "upload_session_id": session_id, "upload_session": upload_session,
            "presign_responses": presign_responses, "complete_responses": complete_responses,
            "finalize_response": finalize_response, "response": finalize_response, "finalize_json": data,
            "report_id": report_id, "report": report_row, "sections": section_rows,
            "attachments": attachment_rows, "storage_objects": storage_rows,
            "section_ids": section_ids, "attachment_ids": [row.id for row in attachment_rows],
            "storage_object_ids": storage_ids, "media_job_ids": media_job_ids}
