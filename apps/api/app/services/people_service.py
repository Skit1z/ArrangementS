"""人员管理：查询、停用/启用、自动排班名单、个人约束、敏感字段查看。"""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_field, encrypt_field, last4
from app.core.pinyin import build_initial_password
from app.core.security import hash_password
from app.models.constraint import PersonConstraint
from app.models.enums import PersonStatus, UserRole
from app.models.person import PersonProfile
from app.models.user import User
from app.services.audit_service import record_audit


def create_person(
    db: Session,
    *,
    student_no: str,
    class_name: str = "",
    full_name: str,
    phone: str,
    difficulty_level: str | None = None,
    id_card: str | None = None,
    bank_card: str | None = None,
    is_in_scheduling_pool: bool = True,
) -> tuple[PersonProfile, str]:
    student_no = student_no.strip()
    class_name = (class_name or "").strip()
    full_name = full_name.strip()
    phone = phone.strip()

    if not student_no or not full_name or not phone:
        raise HTTPException(status_code=400, detail="学号、姓名、手机号不能为空")

    existing = db.scalar(select(PersonProfile).where(PersonProfile.student_no == student_no))
    if existing is not None:
        raise HTTPException(status_code=400, detail=f"学号 {student_no} 已存在")

    existing_user = db.scalar(select(User).where(User.username == student_no))
    if existing_user is not None:
        raise HTTPException(status_code=400, detail=f"账号 {student_no} 已存在")

    id_cipher = None
    id_l4 = None
    if id_card and id_card.strip():
        raw_id = id_card.strip()
        id_cipher = encrypt_field(raw_id)
        id_l4 = last4(raw_id)

    bank_cipher = None
    bank_l4 = None
    if bank_card and bank_card.strip():
        raw_bank = bank_card.strip()
        bank_cipher = encrypt_field(raw_bank)
        bank_l4 = last4(raw_bank)

    initial_pwd = build_initial_password(student_no, full_name)
    user = User(
        username=student_no,
        password_hash=hash_password(initial_pwd),
        role=UserRole.user,
        is_active=True,
    )
    db.add(user)
    db.flush()

    prof = PersonProfile(
        user_id=user.id,
        student_no=student_no,
        class_name=class_name,
        full_name=full_name,
        phone=phone,
        difficulty_level=difficulty_level.strip()
        if difficulty_level and difficulty_level.strip()
        else None,
        id_card_ciphertext=id_cipher,
        id_card_last4=id_l4,
        bank_card_ciphertext=bank_cipher,
        bank_card_last4=bank_l4,
        status=PersonStatus.active,
        is_in_scheduling_pool=is_in_scheduling_pool,
    )
    db.add(prof)
    db.flush()
    return prof, initial_pwd


def get_person(db: Session, person_id: uuid.UUID) -> PersonProfile:
    prof = db.get(PersonProfile, person_id)
    if prof is None:
        raise HTTPException(status_code=404, detail="人员不存在")
    return prof


def get_person_by_user(db: Session, user_id: uuid.UUID) -> PersonProfile:
    prof = db.scalar(select(PersonProfile).where(PersonProfile.user_id == user_id))
    if prof is None:
        raise HTTPException(status_code=404, detail="当前账号未关联人员档案")
    return prof


def list_people(
    db: Session,
    *,
    class_name: str | None = None,
    keyword: str | None = None,
    status_filter: PersonStatus | None = None,
) -> list[PersonProfile]:
    stmt = select(PersonProfile)
    if class_name:
        stmt = stmt.where(PersonProfile.class_name == class_name)
    if status_filter:
        stmt = stmt.where(PersonProfile.status == status_filter)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            (PersonProfile.full_name.like(like)) | (PersonProfile.student_no.like(like))
        )
    stmt = stmt.order_by(PersonProfile.class_name, PersonProfile.student_no)
    return list(db.scalars(stmt))


def set_status(db: Session, person_id: uuid.UUID, new_status: PersonStatus) -> PersonProfile:
    prof = get_person(db, person_id)
    prof.status = new_status
    if prof.user is not None:
        prof.user.is_active = new_status == PersonStatus.active
    db.flush()
    return prof


def set_scheduling_pool(
    db: Session, actor_id: uuid.UUID, person_ids: list[uuid.UUID], enabled: bool
) -> int:
    profs = list(db.scalars(select(PersonProfile).where(PersonProfile.id.in_(person_ids))))
    for prof in profs:
        prof.is_in_scheduling_pool = enabled
    db.flush()
    record_audit(
        db,
        actor_user_id=actor_id,
        action="people.scheduling_pool.update",
        entity_type="person_profile",
        after_data={"person_ids": [str(p.id) for p in profs], "enabled": enabled},
    )
    return len(profs)


# --- 敏感字段查看：admin 二次确认 + 审计 ---
def reveal_sensitive(
    db: Session, actor_id: uuid.UUID, person_id: uuid.UUID, ip: str | None, ua: str | None
) -> dict:
    prof = get_person(db, person_id)
    record_audit(
        db,
        actor_user_id=actor_id,
        action="people.sensitive.reveal",
        entity_type="person_profile",
        entity_id=prof.id,
        reason="admin 查看完整身份证号/银行卡号",
        ip_address=ip,
        user_agent=ua,
    )
    return {
        "id_card": decrypt_field(prof.id_card_ciphertext),
        "bank_card": decrypt_field(prof.bank_card_ciphertext),
    }


# --- 个人约束 ---
def add_constraint(
    db: Session,
    actor_id: uuid.UUID,
    person_id: uuid.UUID,
    constraint_type: str,
    constraint_value: dict | None,
    is_hard: bool,
) -> PersonConstraint:
    get_person(db, person_id)
    c = PersonConstraint(
        person_id=person_id,
        constraint_type=constraint_type,
        constraint_value=constraint_value,
        is_hard=is_hard,
        created_by=actor_id,
    )
    db.add(c)
    db.flush()
    return c


def list_constraints(db: Session, person_id: uuid.UUID) -> list[PersonConstraint]:
    return list(db.scalars(select(PersonConstraint).where(PersonConstraint.person_id == person_id)))


def delete_constraint(db: Session, person_id: uuid.UUID, constraint_id: uuid.UUID) -> None:
    c = db.get(PersonConstraint, constraint_id)
    if c is None or c.person_id != person_id:
        raise HTTPException(status_code=404, detail="约束不存在")
    db.delete(c)
    db.flush()


def update_person(
    db: Session,
    person_id: uuid.UUID,
    patch: dict,
) -> PersonProfile:
    prof = db.get(PersonProfile, person_id)
    if prof is None:
        raise HTTPException(status_code=404, detail="人员不存在")

    if "student_no" in patch and patch["student_no"] is not None:
        new_no = patch["student_no"].strip()
        if new_no and new_no != prof.student_no:
            existing = db.scalar(select(PersonProfile).where(PersonProfile.student_no == new_no))
            if existing is not None:
                raise HTTPException(status_code=400, detail=f"学号 {new_no} 已被占用")
            prof.student_no = new_no
            if prof.user:
                prof.user.username = new_no

    if "full_name" in patch and patch["full_name"] is not None:
        prof.full_name = patch["full_name"].strip()
    if "class_name" in patch and patch["class_name"] is not None:
        prof.class_name = patch["class_name"].strip()
    if "phone" in patch and patch["phone"] is not None:
        prof.phone = patch["phone"].strip()
    if "difficulty_level" in patch:
        prof.difficulty_level = patch["difficulty_level"]
    if "is_in_scheduling_pool" in patch and patch["is_in_scheduling_pool"] is not None:
        prof.is_in_scheduling_pool = patch["is_in_scheduling_pool"]
    if "status" in patch and patch["status"] is not None:
        prof.status = patch["status"]
        if prof.user is not None:
            prof.user.is_active = patch["status"] == PersonStatus.active

    if "id_card" in patch and patch["id_card"] is not None:
        raw_id = patch["id_card"].strip()
        if raw_id:
            prof.id_card_ciphertext = encrypt_field(raw_id)
            prof.id_card_last4 = last4(raw_id)
        else:
            prof.id_card_ciphertext = None
            prof.id_card_last4 = None

    if "bank_card" in patch and patch["bank_card"] is not None:
        raw_bank = patch["bank_card"].strip()
        if raw_bank:
            prof.bank_card_ciphertext = encrypt_field(raw_bank)
            prof.bank_card_last4 = last4(raw_bank)
        else:
            prof.bank_card_ciphertext = None
            prof.bank_card_last4 = None

    db.flush()
    return prof


def delete_person(db: Session, person_id: uuid.UUID) -> None:
    prof = db.get(PersonProfile, person_id)
    if prof is None:
        raise HTTPException(status_code=404, detail="人员不存在")
    user = prof.user

    from app.models.audit import AuditLog
    from app.models.availability import AvailabilityBlock, AvailabilityRequest
    from app.models.constraint import PersonConstraint
    from app.models.import_batch import ImportBatch
    from app.models.leave import LeaveRequest
    from app.models.overtime import OvertimeRequest
    from app.models.schedule import Assignment
    from app.models.statistics import (
        HourAdjustment,
        MonthlyHourSummary,
        MonthlyVenueHourSummary,
    )
    from app.models.swap import SwapCandidate, SwapRequest
    from app.models.timetable import CourseRule, TimetableUpload
    from sqlalchemy import delete, select, update

    # 1. 级联清理人员档案关联数据（约束、排班分配、换班/替班、请假申请、加班申请、月度统计、不可值班、课表）
    db.execute(delete(PersonConstraint).where(PersonConstraint.person_id == person_id))
    db.execute(delete(Assignment).where(Assignment.person_id == person_id))
    db.execute(delete(SwapCandidate).where(SwapCandidate.candidate_person_id == person_id))
    db.execute(
        delete(SwapRequest).where(
            (SwapRequest.requester_person_id == person_id)
            | (SwapRequest.target_person_id == person_id)
            | (SwapRequest.selected_person_id == person_id)
        )
    )
    db.execute(delete(LeaveRequest).where(LeaveRequest.applicant_person_id == person_id))
    db.execute(delete(OvertimeRequest).where(OvertimeRequest.person_id == person_id))
    db.execute(delete(MonthlyHourSummary).where(MonthlyHourSummary.person_id == person_id))
    db.execute(
        delete(MonthlyVenueHourSummary).where(MonthlyVenueHourSummary.person_id == person_id)
    )
    db.execute(delete(HourAdjustment).where(HourAdjustment.person_id == person_id))
    db.execute(delete(AvailabilityBlock).where(AvailabilityBlock.person_id == person_id))
    db.execute(delete(AvailabilityRequest).where(AvailabilityRequest.person_id == person_id))

    uploads = list(
        db.scalars(select(TimetableUpload).where(TimetableUpload.person_id == person_id)).all()
    )
    for up in uploads:
        db.execute(delete(CourseRule).where(CourseRule.timetable_upload_id == up.id))
        db.delete(up)

    if user:
        # 2. 关联用户外键置空（解绑外键）
        db.execute(
            update(TimetableUpload)
            .where(TimetableUpload.uploader_user_id == user.id)
            .values(uploader_user_id=None)
        )
        db.execute(
            update(AuditLog).where(AuditLog.actor_user_id == user.id).values(actor_user_id=None)
        )
        db.execute(
            update(ImportBatch).where(ImportBatch.created_by == user.id).values(created_by=None)
        )

    # 4. 删除档案与关联用户账号
    db.delete(prof)
    if user:
        db.delete(user)
    db.flush()
