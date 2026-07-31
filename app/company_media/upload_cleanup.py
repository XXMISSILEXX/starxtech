"""Database-only cleanup for abandoned Company Media upload selections.

This module deliberately imports neither a storage provider nor media-processing
enqueue code. Object-storage reconciliation is a later operational concern.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select

from app.extensions import db
from app.models import (
    Company,
    CompanyMediaFile,
    DownloadEvent,
    MediaProcessingJob,
    Partner,
    ProjectDocumentFile,
    ReportAttachment,
    StorageDerivative,
    StorageObject,
    SystemSetting,
    UploadBatch,
    UploadBatchItem,
    UploadSelectionSession,
    User,
    UserRole,
)
from app.storage.company_media_errors import upload_error
from app.storage.exceptions import StorageAuthorizationError, StorageValidationError


SCOPE = ("company_media", "album")
NON_COMPLETED_ITEM_STATUSES = {"accepted", "uploading", "failed", "rejected", "cancelled"}
TERMINAL_SESSION_STATUSES = {"completed", "finalized"}


@dataclass(frozen=True)
class CleanupSummary:
    session_id: int
    status: str
    completed_files_preserved: int
    pending_items_removed: int
    pending_storage_objects_removed: int
    protected_storage_objects_preserved: int
    idempotent_replay: bool

    def as_dict(self):
        return {
            "session_id": self.session_id,
            "status": self.status,
            "completed_files_preserved": self.completed_files_preserved,
            "pending_items_removed": self.pending_items_removed,
            "pending_storage_objects_removed": self.pending_storage_objects_removed,
            "protected_storage_objects_preserved": self.protected_storage_objects_preserved,
            "idempotent_replay": self.idempotent_replay,
        }


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _locked_session(session_id):
    return db.session.scalar(
        select(UploadSelectionSession).where(UploadSelectionSession.id == int(session_id))
        .execution_options(populate_existing=True)
        .with_for_update()
    )


def _validate_scope(session, album_id):
    if not session or (session.module_type, session.target_type, session.target_id) != (*SCOPE, int(album_id)):
        raise upload_error("selection_session_target_mismatch", "Phiên tải không thuộc album này.", status_code=403)


def _can_manage_session(actor, session):
    return session.created_by_id == actor.id or actor.role_code in {UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value}


def cancel_company_media_upload_session(*, actor, album_id, session_id):
    """Authorize then clean one Company Media upload session in one transaction."""
    session = _locked_session(session_id)
    _validate_scope(session, album_id)
    if not _can_manage_session(actor, session):
        raise StorageAuthorizationError("Bạn không có quyền hủy phiên tải này.")
    if session.status in TERMINAL_SESSION_STATUSES:
        raise StorageValidationError("Không thể hủy phiên tải đã hoàn tất.")
    return cleanup_company_media_upload_session(session=session, mark_cancelled=True)


def cleanup_company_media_upload_session(*, session=None, session_id=None, mark_cancelled=False):
    """Remove only disposable unfinished Company Media DB rows.

    The caller owns commit/rollback. The selection is always locked and forcibly
    refreshed before inspecting items so PostgreSQL waiters cannot act on stale
    ORM state. No network/provider call is possible from this service.
    """
    # Routes/CLI may already have performed an authorization/query read, which
    # opens SQLAlchemy's outer transaction. A named savepoint gives this shared
    # service an explicit all-or-nothing boundary without committing a caller's
    # work or releasing PostgreSQL row locks early.
    with db.session.begin_nested():
        return _cleanup_company_media_upload_session(
            session=session, session_id=session_id, mark_cancelled=mark_cancelled,
        )


def _cleanup_company_media_upload_session(*, session=None, session_id=None, mark_cancelled=False):
    if session_id is None:
        if session is None:
            raise ValueError("session or session_id is required")
        session_id = session.id
    session = _locked_session(session_id)
    _validate_scope(session, session.target_id if session else 0)
    if session.status in TERMINAL_SESSION_STATUSES:
        raise StorageValidationError("Không thể dọn phiên tải đã hoàn tất.")

    items = db.session.scalars(
        select(UploadBatchItem).where(UploadBatchItem.selection_session_id == session.id)
        .execution_options(populate_existing=True)
        .with_for_update()
    ).all()
    completed = [item for item in items if item.status == "completed"]
    candidates = [item for item in items if item.status in NON_COMPLETED_ITEM_STATUSES]
    if session.cleaned_at is not None:
        return CleanupSummary(
            session_id=session.id, status=session.status, completed_files_preserved=len(completed),
            pending_items_removed=0, pending_storage_objects_removed=0,
            protected_storage_objects_preserved=0, idempotent_replay=True,
        )

    candidate_item_ids = {item.id for item in candidates}
    candidate_object_ids = {item.storage_object_id for item in candidates if item.storage_object_id}
    objects = {
        object_.id: object_
        for object_ in db.session.scalars(
            select(StorageObject).where(StorageObject.id.in_(candidate_object_ids or {-1}))
            .execution_options(populate_existing=True)
            .with_for_update()
        ).all()
    }
    deletable_object_ids = set()
    protected_count = 0
    for object_id, storage_object in objects.items():
        if _storage_object_is_disposable(storage_object, candidate_item_ids):
            deletable_object_ids.add(object_id)
        else:
            protected_count += 1

    for item in candidates:
        db.session.delete(item)
    db.session.flush()

    if deletable_object_ids:
        for object_id in deletable_object_ids:
            db.session.delete(objects[object_id])
        db.session.flush()

    # Batches are request groupings only. A completed item keeps its batch, and
    # a stale/foreign item makes the batch non-empty and therefore retained.
    batches = db.session.scalars(
        select(UploadBatch).where(UploadBatch.selection_session_id == session.id).with_for_update()
    ).all()
    for batch in batches:
        has_items = db.session.scalar(select(UploadBatchItem.id).where(UploadBatchItem.upload_batch_id == batch.id).limit(1))
        if has_items is None:
            db.session.delete(batch)

    if mark_cancelled or session.status != "cancelled":
        session.status = "cancelled"
    session.cleaned_at = _now()
    db.session.flush()
    return CleanupSummary(
        session_id=session.id,
        status=session.status,
        completed_files_preserved=len(completed),
        pending_items_removed=len(candidates),
        pending_storage_objects_removed=len(deletable_object_ids),
        protected_storage_objects_preserved=protected_count,
        idempotent_replay=False,
    )


def _storage_object_is_disposable(storage_object, candidate_item_ids):
    """Fail closed unless a pending original is exclusively disposable now."""
    if storage_object.upload_status != "pending" or storage_object.deleted_at is not None:
        return False
    references = (
        select(UploadBatchItem.id).where(
            UploadBatchItem.storage_object_id == storage_object.id,
            UploadBatchItem.id.not_in(candidate_item_ids or {-1}),
        ),
        select(CompanyMediaFile.id).where(CompanyMediaFile.storage_object_id == storage_object.id),
        select(ProjectDocumentFile.id).where(ProjectDocumentFile.storage_object_id == storage_object.id),
        select(ReportAttachment.id).where(ReportAttachment.storage_object_id == storage_object.id),
        select(StorageDerivative.id).where(StorageDerivative.storage_object_id == storage_object.id),
        select(MediaProcessingJob.id).where(MediaProcessingJob.storage_object_id == storage_object.id),
        select(DownloadEvent.id).where(DownloadEvent.storage_object_id == storage_object.id),
        select(User.id).where(User.avatar_storage_object_id == storage_object.id),
        select(Company.id).where(Company.company_photo_storage_object_id == storage_object.id),
        select(Partner.id).where(Partner.profile_photo_storage_object_id == storage_object.id),
        select(SystemSetting.key).where(SystemSetting.brand_logo_storage_object_id == storage_object.id),
    )
    return not any(db.session.scalar(reference.limit(1)) is not None for reference in references)
