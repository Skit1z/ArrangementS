"""系统配置：倍率规则、特殊日期与节假日同步、审计查询（方案 13.10）。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.config import SystemSetting
from app.models.user import User
from app.schemas.auth import MessageOut
from app.schemas.venue import (
    HolidaySyncConfirm,
    HolidaySyncRequest,
    MultiplierRuleIn,
    MultiplierRuleOut,
    SpecialDateIn,
    SpecialDateOut,
)
from app.services import multiplier_service, special_date_service

router = APIRouter(tags=["config"])


# --- 倍率规则 ---
@router.get("/multiplier-rules", response_model=list[MultiplierRuleOut])
def list_multiplier_rules(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list:
    return multiplier_service.list_rules(db)


@router.post("/multiplier-rules", response_model=MultiplierRuleOut, status_code=201)
def create_multiplier_rule(
    payload: MultiplierRuleIn, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> object:
    rule = multiplier_service.create_rule(db, **payload.model_dump())
    db.commit()
    return rule


@router.patch("/multiplier-rules/{rule_id}", response_model=MultiplierRuleOut)
def update_multiplier_rule(
    rule_id: uuid.UUID,
    payload: MultiplierRuleIn,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> object:
    rule = multiplier_service.update_rule(db, rule_id, payload.model_dump(exclude_unset=True))
    db.commit()
    return rule


@router.post("/multiplier-rules/{rule_id}/disable", response_model=MessageOut)
def disable_multiplier_rule(
    rule_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> MessageOut:
    multiplier_service.disable_rule(db, rule_id)
    db.commit()
    return MessageOut(message="倍率规则已停用")


# --- 特殊日期 ---
@router.get("/special-dates", response_model=list[SpecialDateOut])
def list_special_dates(
    year: int | None = Query(None), _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> list:
    return special_date_service.list_special_dates(db, year)


@router.post("/special-dates", response_model=SpecialDateOut, status_code=201)
def create_special_date(
    payload: SpecialDateIn, actor: User = Depends(require_admin), db: Session = Depends(get_db)
) -> object:
    sd = special_date_service.upsert_special_date(
        db,
        day=payload.date,
        day_type=payload.day_type,
        custom_required_people=payload.custom_required_people,
        reason=payload.reason,
        confirmed_by=actor.id,
    )
    db.commit()
    return sd


@router.post("/special-dates/sync")
def sync_holidays(
    payload: HolidaySyncRequest, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> list[dict]:
    """拉取/导入节假日数据并返回待确认差异列表（不写入）。"""
    data = payload.data or special_date_service.fetch_holiday_json(payload.year, payload.url)
    items = special_date_service.parse_holiday_json(data)
    return special_date_service.preview_sync(db, items)


@router.post("/special-dates/sync/confirm", response_model=MessageOut)
def confirm_sync(
    payload: HolidaySyncConfirm, actor: User = Depends(require_admin), db: Session = Depends(get_db)
) -> MessageOut:
    n = special_date_service.confirm_sync(db, actor.id, payload.items)
    db.commit()
    return MessageOut(message=f"已确认写入 {n} 个特殊日期")


# --- 审计日志 ---
@router.get("/audit-logs")
def list_audit_logs(
    limit: int = Query(100, le=500), _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> list[dict]:
    rows = db.execute(
        select(AuditLog, User)
        .outerjoin(User, AuditLog.actor_user_id == User.id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": str(log.id),
            "actor_user_id": str(log.actor_user_id) if log.actor_user_id else None,
            "actor_username": user.username if user is not None else None,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "reason": log.reason,
            "created_at": log.created_at.isoformat(),
        }
        for log, user in rows
    ]


# --- 系统设置 (K-V) ---
@router.get("/system-settings")
def list_system_settings(
    _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> list[dict]:
    rows = db.scalars(select(SystemSetting).order_by(SystemSetting.key)).all()
    return [
        {"key": r.key, "value": r.value, "description": r.description}
        for r in rows
    ]


@router.put("/system-settings/{key}")
def upsert_system_setting(
    key: str,
    payload: dict,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    if "value" not in payload:
        raise HTTPException(status_code=422, detail="缺少 value 字段")
    value = str(payload["value"])
    description = payload.get("description")
    # 业务校验：寒暑假默认周数 5-8
    if key == "trailing_vacation_weeks":
        try:
            v = int(value)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="value 必须为整数") from None
        if v < 5 or v > 8:
            raise HTTPException(status_code=422, detail="寒暑假默认周数必须在 5-8 之间")
    row = db.get(SystemSetting, key)
    if row is None:
        row = SystemSetting(key=key, value=value, description=description)
        db.add(row)
    else:
        row.value = value
        if description is not None:
            row.description = description
    db.commit()
    return {"key": key, "value": value, "description": description}
