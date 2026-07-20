"""人员管理路由（均为 admin 权限）。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import require_admin
from app.db.session import get_db
from app.models.enums import PersonStatus
from app.models.user import User
from app.schemas.auth import MessageOut
from app.schemas.people import (
    ConstraintCreate,
    ConstraintOut,
    CreatedAccountOut,
    ImportConfirmOut,
    ImportPreviewOut,
    ImportPreviewRow,
    PersonCreateIn,
    PersonCreateOut,
    PersonOut,
    SchedulingPoolRequest,
    SensitiveOut,
)
from app.services import people_import, people_service

router = APIRouter(prefix="/people", tags=["people"])


@router.get("", response_model=list[PersonOut])
def list_people(
    class_name: str | None = Query(None),
    keyword: str | None = Query(None),
    status: PersonStatus | None = Query(None),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[PersonOut]:
    people = people_service.list_people(
        db, class_name=class_name, keyword=keyword, status_filter=status
    )
    return [PersonOut.from_profile(p) for p in people]


@router.post("", response_model=PersonCreateOut, status_code=201)
def create_person(
    payload: PersonCreateIn,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PersonCreateOut:
    """Admin 手动添加单个人员档案及自动开通登录账号。"""
    prof, initial_pwd = people_service.create_person(
        db,
        student_no=payload.student_no,
        class_name=payload.class_name,
        full_name=payload.full_name,
        phone=payload.phone,
        difficulty_level=payload.difficulty_level,
        id_card=payload.id_card,
        bank_card=payload.bank_card,
        is_in_scheduling_pool=payload.is_in_scheduling_pool,
    )
    db.commit()
    return PersonCreateOut(
        person=PersonOut.from_profile(prof),
        initial_password=initial_pwd,
    )


@router.get("/{person_id}", response_model=PersonOut)
def get_person(
    person_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> PersonOut:
    return PersonOut.from_profile(people_service.get_person(db, person_id))


@router.get("/import/template")
def download_import_template(_: User = Depends(require_admin)) -> Response:
    import io
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["学号", "班级", "姓名", "手机号", "困难等级", "身份证号", "银行卡号"])
    ws.append(
        [
            "2023000001",
            "计科2301",
            "张三",
            "13800138000",
            "A",
            "110105200001011234",
            "6222021001112222",
        ]
    )

    bio = io.BytesIO()
    wb.save(bio)
    return Response(
        content=bio.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="import_template.xlsx"'},
    )


@router.post("/import/preview", response_model=ImportPreviewOut)
async def import_preview(
    file: UploadFile = File(...),
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ImportPreviewOut:
    content = await file.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        from fastapi import HTTPException

        raise HTTPException(status_code=413, detail="文件过大")
    batch = people_import.create_preview(db, file.filename or "import.xlsx", content, actor.id)
    db.commit()
    payload = batch.preview_payload or {}
    return ImportPreviewOut(
        batch_id=batch.id,
        total_rows=batch.total_rows,
        new_rows=batch.new_rows,
        updated_rows=batch.updated_rows,
        error_rows=batch.error_rows,
        rows=[
            ImportPreviewRow(**{k: r[k] for k in ImportPreviewRow.model_fields})
            for r in payload.get("rows", [])
        ],
    )


@router.post("/import/{batch_id}/confirm", response_model=ImportConfirmOut)
def import_confirm(
    batch_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> ImportConfirmOut:
    created = people_import.confirm_import(db, batch_id)
    db.commit()
    return ImportConfirmOut(
        created_count=len(created),
        accounts=[CreatedAccountOut(**c.__dict__) for c in created],
    )


@router.put("/scheduling-pool", response_model=MessageOut)
def update_scheduling_pool(
    payload: SchedulingPoolRequest,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageOut:
    n = people_service.set_scheduling_pool(db, actor.id, payload.person_ids, payload.enabled)
    db.commit()
    return MessageOut(message=f"已更新 {n} 人的自动排班参与状态")


@router.post("/{person_id}/suspend", response_model=PersonOut)
def suspend_person(
    person_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> PersonOut:
    prof = people_service.set_status(db, person_id, PersonStatus.suspended)
    db.commit()
    return PersonOut.from_profile(prof)


@router.post("/{person_id}/activate", response_model=PersonOut)
def activate_person(
    person_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> PersonOut:
    prof = people_service.set_status(db, person_id, PersonStatus.active)
    db.commit()
    return PersonOut.from_profile(prof)


@router.get("/{person_id}/sensitive", response_model=SensitiveOut)
def reveal_sensitive(
    person_id: uuid.UUID,
    request: Request,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SensitiveOut:
    data = people_service.reveal_sensitive(
        db,
        actor.id,
        person_id,
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )
    db.commit()
    return SensitiveOut(**data)


@router.get("/{person_id}/constraints", response_model=list[ConstraintOut])
def list_constraints(
    person_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> list[ConstraintOut]:
    return [ConstraintOut.model_validate(c) for c in people_service.list_constraints(db, person_id)]


@router.post("/{person_id}/constraints", response_model=ConstraintOut, status_code=201)
def add_constraint(
    person_id: uuid.UUID,
    payload: ConstraintCreate,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ConstraintOut:
    c = people_service.add_constraint(
        db, actor.id, person_id, payload.constraint_type, payload.constraint_value, payload.is_hard
    )
    db.commit()
    return ConstraintOut.model_validate(c)


@router.delete("/{person_id}/constraints/{constraint_id}", response_model=MessageOut)
def delete_constraint(
    person_id: uuid.UUID,
    constraint_id: uuid.UUID,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageOut:
    people_service.delete_constraint(db, person_id, constraint_id)
    db.commit()
    return MessageOut(message="约束已删除")
