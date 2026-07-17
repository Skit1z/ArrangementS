"""特殊日期与法定节假日同步（方案 2.9）。

红线：同步数据必须先进入待确认，admin 确认后才写入生效，绝不静默生效。
数据源：holiday-cn（按年份 JSON，isOffDay=true 为节假日，false 为补班调休工作日）。
无外网时可手动录入或手动导入 JSON，功能不受影响。
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from urllib.request import urlopen

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import DayType, SpecialDateSource
from app.models.special_date import SpecialDate

HOLIDAY_URL_TEMPLATE = (
    "https://raw.githubusercontent.com/NateScarlet/holiday-cn/master/{year}.json"
)


def get_special_date(db: Session, day: date) -> SpecialDate | None:
    return db.scalar(select(SpecialDate).where(SpecialDate.date == day))


def list_special_dates(db: Session, year: int | None = None) -> list[SpecialDate]:
    stmt = select(SpecialDate).order_by(SpecialDate.date)
    if year is not None:
        stmt = stmt.where(
            SpecialDate.date >= date(year, 1, 1), SpecialDate.date <= date(year, 12, 31)
        )
    return list(db.scalars(stmt))


def upsert_special_date(
    db: Session,
    *,
    day: date,
    day_type: DayType,
    custom_required_people: int | None = None,
    reason: str | None = None,
    source: SpecialDateSource = SpecialDateSource.manual,
    confirmed_by: uuid.UUID | None = None,
) -> SpecialDate:
    if day_type == DayType.custom and custom_required_people is None:
        raise HTTPException(status_code=422, detail="自定义类型必须提供人数")
    sd = get_special_date(db, day)
    now = datetime.now(timezone.utc)
    if sd is None:
        sd = SpecialDate(date=day)
        db.add(sd)
    sd.day_type = day_type
    sd.custom_required_people = custom_required_people
    sd.reason = reason
    sd.source = source
    if source == SpecialDateSource.holiday_sync or confirmed_by is not None:
        sd.confirmed_by = confirmed_by
        sd.confirmed_at = now
    db.flush()
    return sd


# --- 节假日同步 ---
def parse_holiday_json(data: dict) -> list[dict]:
    """解析 holiday-cn JSON 为待确认项列表（纯函数，便于测试）。"""
    items: list[dict] = []
    for entry in data.get("days", []):
        try:
            d = date.fromisoformat(entry["date"])
        except (KeyError, ValueError):
            continue
        is_off = bool(entry.get("isOffDay"))
        items.append(
            {
                "date": d.isoformat(),
                "day_type": (DayType.weekend_rule if is_off else DayType.workday).value,
                "reason": entry.get("name"),
                "is_off_day": is_off,
            }
        )
    return items


def fetch_holiday_json(year: int, url: str | None = None) -> dict:
    target = url or HOLIDAY_URL_TEMPLATE.format(year=year)
    try:
        with urlopen(target, timeout=10) as resp:  # noqa: S310 - 固定可信数据源
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502, detail=f"节假日数据源不可达：{exc}（可手动导入 JSON 或手动录入）"
        ) from exc


def preview_sync(db: Session, items: list[dict]) -> list[dict]:
    """对比同步项与现有特殊日期，标注 new / same / conflict，供 admin 逐条决定。"""
    result: list[dict] = []
    for item in items:
        d = date.fromisoformat(item["date"])
        existing = get_special_date(db, d)
        if existing is None:
            status = "new"
        elif existing.day_type.value == item["day_type"]:
            status = "same"
        else:
            status = "conflict"
        result.append(
            {
                **item,
                "status": status,
                "existing_day_type": existing.day_type.value if existing else None,
            }
        )
    return result


def confirm_sync(db: Session, actor_id: uuid.UUID, items: list[dict]) -> int:
    """admin 确认后写入（仅写入被采纳的项）。"""
    count = 0
    for item in items:
        d = date.fromisoformat(item["date"])
        upsert_special_date(
            db,
            day=d,
            day_type=DayType(item["day_type"]),
            reason=item.get("reason"),
            source=SpecialDateSource.holiday_sync,
            confirmed_by=actor_id,
        )
        count += 1
    return count
