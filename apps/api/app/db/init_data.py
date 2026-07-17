"""初始化基础数据：默认 admin。

场地、黄楼班次模板、倍率规则等将在阶段四建模后补充到本脚本
（保持幂等：已存在则跳过）。运行：`python -m app.db.init_data`。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.enums import UserRole
from app.models.user import User

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin1234"  # 首次登录后应修改（方案 3.2）


def ensure_default_admin() -> None:
    with SessionLocal() as db:
        exists = db.scalar(select(User).where(User.username == DEFAULT_ADMIN_USERNAME))
        if exists is not None:
            print(f"默认 admin 已存在：{DEFAULT_ADMIN_USERNAME}")
            return
        admin = User(
            username=DEFAULT_ADMIN_USERNAME,
            password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
            role=UserRole.admin,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        print(f"已创建默认 admin：{DEFAULT_ADMIN_USERNAME} / {DEFAULT_ADMIN_PASSWORD}（请尽快修改）")


def main() -> None:
    ensure_default_admin()


if __name__ == "__main__":
    main()
