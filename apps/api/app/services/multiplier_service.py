"""倍率规则服务：DB 规则 <-> 工时引擎规则映射、重叠校验、CRUD（方案 2.6）。"""

from __future__ import annotations

import uuid
from datetime import time
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.multiplier import MultiplierRule as DBRule
from app.services.hours import MultiplierConfigError
from app.services.hours import MultiplierRule as EngineRule
from app.services.hours import validate_multiplier_rules


def _minutes(t: time, *, is_end: bool) -> int:
    m = t.hour * 60 + t.minute
    if is_end and m == 0:
        return 1440  # 00:00 作为结束时间表示 24:00
    return m


def to_engine_rule(db_rule: DBRule) -> EngineRule:
    return EngineRule(
        name=db_rule.name,
        start_min=_minutes(db_rule.start_time, is_end=False),
        end_min=_minutes(db_rule.end_time, is_end=True),
        multiplier=Decimal(db_rule.multiplier),
        priority=db_rule.priority,
        venue_id=str(db_rule.venue_id) if db_rule.venue_id else None,
        weekdays=frozenset(db_rule.weekdays) if db_rule.weekdays else None,
        effective_start_date=db_rule.effective_start_date,
        effective_end_date=db_rule.effective_end_date,
        is_active=db_rule.is_active,
    )


def load_engine_rules(db: Session) -> list[EngineRule]:
    rules = db.scalars(select(DBRule).where(DBRule.is_active.is_(True)))
    return [to_engine_rule(r) for r in rules]


def _assert_valid(
    db: Session, extra: DBRule | None = None, exclude_id: uuid.UUID | None = None
) -> None:
    rows = list(db.scalars(select(DBRule).where(DBRule.is_active.is_(True))))
    engine_rules = [to_engine_rule(r) for r in rows if r.id != exclude_id]
    if extra is not None and extra.is_active:
        engine_rules.append(to_engine_rule(extra))
    try:
        validate_multiplier_rules(engine_rules)
    except MultiplierConfigError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def create_rule(db: Session, **fields) -> DBRule:
    rule = DBRule(**fields)
    _assert_valid(db, extra=rule)
    db.add(rule)
    db.flush()
    return rule


def update_rule(db: Session, rule_id: uuid.UUID, patch: dict) -> DBRule:
    rule = db.get(DBRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="倍率规则不存在")
    for k, v in patch.items():
        setattr(rule, k, v)
    _assert_valid(db, extra=rule, exclude_id=rule.id)
    db.flush()
    return rule


def disable_rule(db: Session, rule_id: uuid.UUID) -> DBRule:
    rule = db.get(DBRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="倍率规则不存在")
    rule.is_active = False
    db.flush()
    return rule


def list_rules(db: Session) -> list[DBRule]:
    return list(db.scalars(select(DBRule).order_by(DBRule.priority.desc())))
