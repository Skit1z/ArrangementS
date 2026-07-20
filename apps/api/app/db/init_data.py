"""初始化基础数据：默认 admin、三场地、黄楼六班次、默认倍率规则。

幂等：已存在则跳过。运行：`python -m app.db.init_data`。
"""

from __future__ import annotations

from datetime import time
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.enums import UserRole, VenueType
from app.models.multiplier import MultiplierRule
from app.models.user import User
from app.models.venue import ShiftTemplate, Venue

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin1234"  # 首次登录后应修改（方案 3.2）

# 黄楼六班次：实际时间不同，但统计工时固定 120 分钟（方案 2.2）
YELLOW_SHIFTS = [
    ("第1班", time(8, 0), time(10, 0)),
    ("第2班", time(10, 0), time(12, 0)),
    ("第3班", time(12, 0), time(14, 0)),
    ("第4班", time(14, 0), time(16, 0)),
    ("第5班", time(16, 0), time(17, 30)),
    ("第6班", time(17, 30), time(19, 0)),
]


def ensure_default_admin(db: Session) -> None:
    if db.scalar(select(User).where(User.username == DEFAULT_ADMIN_USERNAME)):
        print(f"默认 admin 已存在：{DEFAULT_ADMIN_USERNAME}")
        return
    db.add(
        User(
            username=DEFAULT_ADMIN_USERNAME,
            password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
            role=UserRole.admin,
            is_active=True,
        )
    )
    print(f"已创建默认 admin：{DEFAULT_ADMIN_USERNAME} / {DEFAULT_ADMIN_PASSWORD}（请尽快修改）")


def ensure_venues(db: Session) -> None:
    if db.scalar(select(Venue)):
        print("场地已存在，跳过初始化")
        return
    yellow = Venue(
        name="黄楼",
        code="HL",
        venue_type=VenueType.fixed_shift,
        default_required_people=2,
        sort_order=1,
    )
    db.add(yellow)
    db.flush()
    for idx, (name, start, end) in enumerate(YELLOW_SHIFTS):
        db.add(
            ShiftTemplate(
                venue_id=yellow.id,
                name=name,
                start_time=start,
                end_time=end,
                credited_minutes=120,
                weekday_required_people=2,
                weekend_required_people=1,
                sort_order=idx,
            )
        )
    db.add(
        Venue(
            name="蓝厅",
            code="LT",
            venue_type=VenueType.event_based,
            default_required_people=2,
            sort_order=2,
        )
    )
    db.add(
        Venue(
            name="图书馆报告厅",
            code="TSG",
            venue_type=VenueType.event_based,
            default_required_people=2,
            sort_order=3,
        )
    )
    print("已初始化三场地与黄楼六班次")


def ensure_multiplier_rules(db: Session) -> None:
    if db.scalar(select(MultiplierRule)):
        print("倍率规则已存在，跳过初始化")
        return
    db.add(
        MultiplierRule(
            name="早间双倍",
            start_time=time(0, 0),
            end_time=time(8, 0),
            multiplier=Decimal("2.0"),
            priority=10,
            is_active=True,
        )
    )
    db.add(
        MultiplierRule(
            name="晚间双倍",
            start_time=time(19, 0),
            end_time=time(0, 0),  # 00:00 表示 24:00
            multiplier=Decimal("2.0"),
            priority=10,
            is_active=True,
        )
    )
    print("已初始化默认倍率规则（早间/晚间双倍）")


def main() -> None:
    with SessionLocal() as db:
        ensure_default_admin(db)
        ensure_venues(db)
        ensure_multiplier_rules(db)
        db.commit()


if __name__ == "__main__":
    main()
