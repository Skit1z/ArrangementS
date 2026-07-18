from datetime import timedelta
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin, require_person
from app.db.session import get_db
from app.models.enums import RequestStatus, SlotSourceType, SlotStatus, PlanAssignmentStatus, ExecutionStatus, AssignmentSource
from app.models.overtime import OvertimeRequest
from app.models.person import PersonProfile
from app.models.schedule import DutySlot, WeeklyPlan, Assignment
from app.models.user import User
from app.models.venue import Venue
from app.schemas.auth import MessageOut
from app.schemas.manual_slot import ManualSlotCreate
from app.schemas.overtime import OvertimeRequestCreate, OvertimeRequestOut
from app.services import schedule_service

router = APIRouter(tags=["overtime"])

@router.post("/me/overtime", response_model=MessageOut)
def apply_overtime(
    payload: OvertimeRequestCreate,
    person: PersonProfile = Depends(require_person),
    db: Session = Depends(get_db),
):
    if payload.end_at <= payload.start_at:
        raise HTTPException(status_code=400, detail="结束时间必须晚于开始时间")
    
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
    person: PersonProfile = Depends(require_person),
    db: Session = Depends(get_db),
):
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

def get_or_create_plan_for_date(db: Session, target_date):
    # Find the Monday of the week
    week_start = target_date.date() - timedelta(days=target_date.weekday())
    week_end = week_start + timedelta(days=6)
    plan = db.query(WeeklyPlan).filter(WeeklyPlan.week_start == week_start).first()
    if not plan:
        plan = WeeklyPlan(
            week_start=week_start,
            week_end=week_end,
        )
        db.add(plan)
        db.flush()
    return plan

@router.post("/admin/overtime/{req_id}/approve", response_model=MessageOut)
def approve_overtime(
    req_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    req = db.query(OvertimeRequest).filter(OvertimeRequest.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="申请不存在")
    if req.status != RequestStatus.pending:
        raise HTTPException(status_code=400, detail="该申请已被处理")

    req.status = RequestStatus.approved
    req.reviewed_by = admin.id
    req.reviewed_at = datetime.now()

    # Create slot and assignment
    plan = get_or_create_plan_for_date(db, req.start_at)
    minutes = int((req.end_at - req.start_at).total_seconds() / 60)
    
    slot = DutySlot(
        weekly_plan_id=plan.id,
        venue_id=req.venue_id,
        source_type=SlotSourceType.manual,
        slot_start_at=req.start_at,
        slot_end_at=req.end_at,
        required_people=1,
        credited_minutes=minutes,
        month_key=req.start_at.strftime("%Y-%m"),
        status=SlotStatus.filled
    )
    db.add(slot)
    db.flush()
    
    assignment = Assignment(
        duty_slot_id=slot.id,
        person_id=req.person_id,
        position_index=0,
        assignment_source=AssignmentSource.manual,
        plan_status=PlanAssignmentStatus.assigned,
        execution_status=ExecutionStatus.pending,
        raw_minutes=minutes,
        credited_minutes=minutes,
        balance_minutes=minutes
    )
    db.add(assignment)
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
    if payload.end_at <= payload.start_at:
        raise HTTPException(status_code=400, detail="结束时间必须晚于开始时间")
        
    plan = get_or_create_plan_for_date(db, payload.start_at)
    minutes = int((payload.end_at - payload.start_at).total_seconds() / 60)
    
    slot = DutySlot(
        weekly_plan_id=plan.id,
        venue_id=payload.venue_id,
        source_type=SlotSourceType.manual,
        slot_start_at=payload.start_at,
        slot_end_at=payload.end_at,
        required_people=payload.required_people,
        credited_minutes=minutes,
        month_key=payload.start_at.strftime("%Y-%m"),
        status=SlotStatus.open
    )
    db.add(slot)
    db.flush()
    
    for i in range(payload.required_people):
        assignment = Assignment(
            duty_slot_id=slot.id,
            person_id=None,
            position_index=i,
            assignment_source=AssignmentSource.auto,
            plan_status=PlanAssignmentStatus.vacant,
            execution_status=ExecutionStatus.pending,
            raw_minutes=minutes,
            credited_minutes=minutes,
            balance_minutes=minutes
        )
        db.add(assignment)
        
    db.commit()
    return MessageOut(message="临时班次已创建")
