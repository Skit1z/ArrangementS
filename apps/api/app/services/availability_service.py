"""不可值班申请与区间（方案 5.2）。用户提交 -> admin 审核 -> 生成不可值班区间。"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.availability import AvailabilityBlock, AvailabilityRequest
from app.models.enums import AvailabilitySource, AvailabilityStatus, RequestStatus
from app.services.audit_service import record_audit


def create_request(
    db: Session, *, person_id: uuid.UUID, start_at: datetime, end_at: datetime, reason: str,
    recurrence_rule: str | None = None,
) -> AvailabilityRequest:
    if end_at <= start_at:
        raise HTTPException(status_code=422, detail="结束时间必须晚于开始时间")
    now = datetime.now(timezone.utc)
    end_cmp = end_at.replace(tzinfo=timezone.utc) if end_at.tzinfo is None else end_at
    if end_cmp < now:
        raise HTTPException(status_code=422, detail="不能对已过期时间提交申请")
    req = AvailabilityRequest(
        person_id=person_id, start_at=start_at, end_at=end_at, reason=reason,
        recurrence_rule=recurrence_rule, status=RequestStatus.pending,
    )
    db.add(req)
    db.flush()
    return req


def list_my(db: Session, person_id: uuid.UUID) -> list[AvailabilityRequest]:
    return list(
        db.scalars(
            select(AvailabilityRequest)
            .where(AvailabilityRequest.person_id == person_id)
            .order_by(AvailabilityRequest.created_at.desc())
        )
    )


def list_pending(db: Session) -> list[AvailabilityRequest]:
    return list(
        db.scalars(select(AvailabilityRequest).where(AvailabilityRequest.status == RequestStatus.pending))
    )


def withdraw(db: Session, person_id: uuid.UUID, request_id: uuid.UUID) -> AvailabilityRequest:
    req = _get(db, request_id)
    if req.person_id != person_id:
        raise HTTPException(status_code=403, detail="只能撤回本人申请")
    if req.status != RequestStatus.pending:
        raise HTTPException(status_code=422, detail="仅待审核申请可撤回")
    req.status = RequestStatus.withdrawn
    db.flush()
    return req


def approve(db: Session, actor_id: uuid.UUID | None, request_id: uuid.UUID) -> AvailabilityRequest:
    req = _get(db, request_id)
    if req.status != RequestStatus.pending:
        raise HTTPException(status_code=422, detail="仅待审核申请可批准")
    now = datetime.now(timezone.utc)
    req.status = RequestStatus.approved
    req.reviewer_id = actor_id
    req.reviewed_at = now
    db.add(
        AvailabilityBlock(
            person_id=req.person_id, source=AvailabilitySource.user_request,
            start_at=req.start_at, end_at=req.end_at, status=AvailabilityStatus.active,
            reason=req.reason, source_ref_id=req.id, approved_by=actor_id, approved_at=now,
        )
    )
    db.flush()
    record_audit(
        db, actor_user_id=actor_id, action="availability_request.approve",
        entity_type="availability_request", entity_id=req.id,
    )
    return req


def reject(db: Session, actor_id: uuid.UUID | None, request_id: uuid.UUID, comment: str | None = None) -> AvailabilityRequest:
    req = _get(db, request_id)
    if req.status != RequestStatus.pending:
        raise HTTPException(status_code=422, detail="仅待审核申请可拒绝")
    req.status = RequestStatus.rejected
    req.reviewer_id = actor_id
    req.review_comment = comment
    req.reviewed_at = datetime.now(timezone.utc)
    db.flush()
    return req


def admin_create_block(
    db: Session, *, actor_id: uuid.UUID | None, person_id: uuid.UUID, start_at: datetime,
    end_at: datetime, reason: str | None = None,
) -> AvailabilityBlock:
    """admin 直接设置不可值班区间（直接生效）。"""
    if end_at <= start_at:
        raise HTTPException(status_code=422, detail="结束时间必须晚于开始时间")
    now = datetime.now(timezone.utc)
    block = AvailabilityBlock(
        person_id=person_id, source=AvailabilitySource.admin, start_at=start_at, end_at=end_at,
        status=AvailabilityStatus.active, reason=reason, approved_by=actor_id, approved_at=now,
    )
    db.add(block)
    db.flush()
    return block


def list_my_blocks(db: Session, person_id: uuid.UUID) -> list[AvailabilityBlock]:
    return list(
        db.scalars(
            select(AvailabilityBlock)
            .where(
                AvailabilityBlock.person_id == person_id,
                AvailabilityBlock.status == AvailabilityStatus.active,
            )
            .order_by(AvailabilityBlock.start_at)
        )
    )


def _get(db: Session, request_id: uuid.UUID) -> AvailabilityRequest:
    req = db.get(AvailabilityRequest, request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="申请不存在")
    return req
