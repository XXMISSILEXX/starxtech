"""Exercise the Daily Report browser upload contract in integration tests."""
from dataclasses import dataclass
import json
from uuid import uuid4

from sqlalchemy import select
from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.models import (DailyReport, DailyReportSection, ReportAttachment,
                        StorageObject, UploadBatchItem, UploadSelectionSession)


@dataclass(frozen=True)
class ReportUploadFile:
    data: bytes
    filename: str = "photo.jpg"
    mime_type: str = "image/jpeg"
    section_index: int = 0
    client_section_id: str | None = None


def submit_report_with_direct_upload(client, app, *, project_id, form, files, submit_url=None):
    """Create, presign, fake-upload, complete, and submit a report form.

    The helper deliberately uses HTTP endpoints for every direct-upload state
    transition; it only writes raw bytes through the configured fake provider,
    which is the browser-to-object-storage step the Flask test client cannot do.
    """
    form = form if hasattr(form, "setlist") else MultiDict(form)
    files = [_coerce_file(file) for file in files]
    assert files, "direct-upload helper requires at least one file"
    session_response = client.post(
        f"/reports/projects/{project_id}/reports/upload-sessions",
        json={"file_count": len(files), "total_size_bytes": sum(len(file.data) for file in files)},
    )
    assert session_response.status_code == 200, session_response.get_data(as_text=True)
    session_id = session_response.get_json()["upload_session_id"]

    client_ids = [f"test-{uuid4().hex}" for _ in files]
    section_ids = {
        file.section_index: file.client_section_id or f"section-{file.section_index}-{uuid4().hex}"
        for file in files
    }
    presign_response = client.post(
        f"/reports/projects/{project_id}/reports/upload-sessions/{session_id}/presign",
        json={"files": [
            {
                "client_file_id": client_id,
                "client_section_id": section_ids[file.section_index],
                "filename": file.filename,
                "mime_type": file.mime_type,
                "size": len(file.data),
            }
            for client_id, file in zip(client_ids, files)
        ]},
    )
    assert presign_response.status_code == 200, presign_response.get_data(as_text=True)
    items = presign_response.get_json()["items"]
    provider = app.extensions["storage_provider"]
    for item, file in zip(items, files):
        with app.app_context():
            storage = db.session.get(StorageObject, item["storage_object_id"])
            provider.put_bytes(storage.bucket, storage.object_key, file.data, storage.mime_type)
        complete_response = client.post(
            f"/reports/projects/{project_id}/reports/upload-sessions/{session_id}/complete",
            json={"upload_batch_item_id": item["upload_batch_item_id"]},
        )
        assert complete_response.status_code == 200, complete_response.get_data(as_text=True)

    for index, client_section_id in section_ids.items():
        form.setlist(f"sections-{index}-client-section-id", [client_section_id])
    form["upload_session_id"] = str(session_id)
    form["direct_upload_expected"] = "1"
    form["direct_upload_selected_count"] = str(len(files))
    form["attachment_manifest"] = json.dumps({
        "upload_session_id": session_id,
        "attachments": [
            {
                "upload_item_id": item["upload_batch_item_id"],
                "client_section_id": section_ids[file.section_index],
                "sort_order": index,
            }
            for index, (item, file) in enumerate(zip(items, files))
        ],
    })
    response = client.post(submit_url or f"/reports/projects/{project_id}/reports/create", data=form)

    with app.app_context():
        report = db.session.scalar(select(DailyReport).where(
            DailyReport.project_id == project_id,
            DailyReport.report_date == _report_date(form["report_date"]),
        ))
        report_id = report.id if report else None
        sections = db.session.scalars(select(DailyReportSection).where(
            DailyReportSection.daily_report_id == report_id
        )).all() if report_id else []
        attachments = db.session.scalars(select(ReportAttachment).join(DailyReportSection).where(
            DailyReportSection.daily_report_id == report_id
        )).all() if report_id else []
        storage_objects = [db.session.get(StorageObject, item["storage_object_id"]) for item in items]
        upload_items = [db.session.get(UploadBatchItem, item["upload_batch_item_id"]) for item in items]
        session = db.session.get(UploadSelectionSession, session_id)
    return {
        "response": response,
        "report": report,
        "sections": sections,
        "attachments": attachments,
        "storage_objects": storage_objects,
        "upload_session": session,
        "upload_items": upload_items,
        "client_section_ids": section_ids,
    }


def _coerce_file(file):
    return file if isinstance(file, ReportUploadFile) else ReportUploadFile(**file)


def _report_date(value):
    from app.reports.services import parse_report_date
    return parse_report_date(value)
