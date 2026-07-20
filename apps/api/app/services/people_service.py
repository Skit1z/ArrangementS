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
    class_name: str,
    full_name: str,
    phone: str,
    difficulty_level: str | None = None,
    id_card: str | None = None,
    bank_card: str | None = None,
    is_in_scheduling_pool: bool = True,
) -> tuple[PersonProfile, str]:
    student_no = student_no.strip()
    class_name = class_name.strip()
    full_name = full_name.strip()
    phone = phone.strip()

    if not student_no or not class_name or not full_name or not phone:
        raise HTTPException(status_code=400, detail="学号、班级、姓名、手机号不能为空")

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
