from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.enums import RequestStatus, SlotSourceType
from app.models.overtime import OvertimeRequest
from app.models.person import PersonProfile
from app.models.user import User
from app.models.venue import Venue
from app.schemas.auth import MessageOut
from app.schemas.manual_slot import ManualSlotCreate
from app.schemas.overtime import OvertimeRequestCreate, OvertimeRequestOut

router = APIRouter(tags=["overtime"])


@router.post("/me/overtime", response_model=MessageOut)
def apply_overtime(
    payload: OvertimeRequestCreate,
    u: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.end_at <= payload.start_at:
        raise HTTPException(status_code=400, detail="结束时间必须晚于开始时间")

    person = db.query(PersonProfile).filter(PersonProfile.user_id == u.id).first()
    if not person:
        raise HTTPException(status_code=403, detail="人员信息不存在")

    req = OvertimeRequest(
        person_id=person.id,
        venue_id=payload.venue_id,
        start_at=payload.start_at,
        end_at=payload.end_at,
        reason=payload.reason,
        status=RequestStatus.pending,
    )
    db.add(req)
    db.commit()
    return MessageOut(message="加班申请已提交，等待审核")


@router.get("/me/overtime", response_model=list[OvertimeRequestOut])
def list_my_overtime(
    u: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    person = db.query(PersonProfile).filter(PersonProfile.user_id == u.id).first()
    if not person:
        raise HTTPException(status_code=403, detail="人员信息不存在")

    reqs = (
        db.query(OvertimeRequest, Venue.name)
        .join(Venue, Venue.id == OvertimeRequest.venue_id)
        .filter(OvertimeRequest.person_id == person.id)
        .order_by(OvertimeRequest.created_at.desc())
        .all()
    )
    res = []
    for r, venue_name in reqs:
        out = OvertimeRequestOut(
            id=r.id,
            person_id=r.person_id,
            person_name=person.full_name,
            venue_id=r.venue_id,
            venue_name=venue_name,
            start_at=r.start_at,
            end_at=r.end_at,
            reason=r.reason,
            status=r.status,
            reviewed_by=r.reviewed_by,
            reviewed_at=r.reviewed_at,
            created_at=r.created_at,
        )
        res.append(out)
    return res


@router.get("/admin/overtime", response_model=list[OvertimeRequestOut])
def list_all_overtime(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    reqs = (
        db.query(OvertimeRequest, Venue.name, PersonProfile.full_name)
        .join(Venue, Venue.id == OvertimeRequest.venue_id)
        .join(PersonProfile, PersonProfile.id == OvertimeRequest.person_id)
        .order_by(OvertimeRequest.created_at.desc())
        .all()
    )
    res = []
    for r, venue_name, person_name in reqs:
        out = OvertimeRequestOut(
            id=r.id,
            person_id=r.person_id,
            person_name=person_name,
            venue_id=r.venue_id,
            venue_name=venue_name,
            start_at=r.start_at,
            end_at=r.end_at,
            reason=r.reason,
            status=r.status,
            reviewed_by=r.reviewed_by,
            reviewed_at=r.reviewed_at,
            created_at=r.created_at,
        )
        res.append(out)
    return res


@router.post("/admin/overtime/{req_id}/approve", response_model=MessageOut)
def approve_overtime(
    req_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """批准加班申请：走核心排班规则（冲突/课程/不可值班/倍率/取整/审计）。

    若该人在此时段存在课程/不可值班区间/场地硬约束/时间重叠，会被拒绝，申请保持 pending。
    """
    from app.services import manual_scheduling_service

    req = db.query(OvertimeRequest).filter(OvertimeRequest.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="申请不存在")
    if req.status != RequestStatus.pending:
        raise HTTPException(status_code=400, detail="该申请已被处理")

    # 走核心规则（失败会抛 HTTPException 422）
    slot, assignment = manual_scheduling_service.assign_person_to_new_slot(
        db,
        person_id=req.person_id,
        venue_id=req.venue_id,
        start_at=req.start_at,
        end_at=req.end_at,
        source_type=SlotSourceType.manual,
        created_by=admin.id,
        action="overtime.approve",
    )

    req.status = RequestStatus.approved
    req.reviewed_by = admin.id
    req.reviewed_at = datetime.now()
    req.generated_slot_id = slot.id

    db.commit()
    return MessageOut(message="已批准并自动生成排班")


@router.post("/admin/overtime/{req_id}/reject", response_model=MessageOut)
def reject_overtime(
    req_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    req = db.query(OvertimeRequest).filter(OvertimeRequest.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="申请不存在")
    if req.status != RequestStatus.pending:
        raise HTTPException(status_code=400, detail="该申请已被处理")

    req.status = RequestStatus.rejected
    req.reviewed_by = admin.id
    req.reviewed_at = datetime.now()
    db.commit()
    return MessageOut(message="已拒绝")


@router.post("/admin/duty-slots/manual", response_model=MessageOut)
def create_manual_slot(
    payload: ManualSlotCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """创建临时空缺班次（无人员）：balance 全部为 0，不污染统计。

    走 ``manual_scheduling_service.create_vacant_slot``，与核心模型一致。
    """
    from app.services import manual_scheduling_service

    manual_scheduling_service.create_vacant_slot(
        db,
        venue_id=payload.venue_id,
        start_at=payload.start_at,
        end_at=payload.end_at,
        required_people=payload.required_people,
        created_by=admin.id,
    )
    db.commit()
    return MessageOut(message="临时班次已创建")
