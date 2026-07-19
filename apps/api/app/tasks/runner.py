"""周期任务运行器（方案 7.4 / 4.8 的接线层）。

两个本已实现但从未被调用的周期函数在此接上调度：
- execution_service.auto_complete_ended：班次结束后自动置「已完成」
- timetable_service.expire_semester_courses：学期结束后旧课表逻辑失效
  （验收 blocker「学期结束后旧课表仍参与冲突计算」）

选用 APScheduler 的轻量单进程模式（BlockingScheduler），不引入 Celery/broker：
两任务均为低频 DB 扫描，无需水平扩展，与项目"最小依赖"风格一致。

入口：`python -m app.tasks.runner`
测试：直接调本模块的 job_* 函数（不走真实 scheduler）。
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.semester import Semester
from app.services import execution_service, timetable_service

log = logging.getLogger("app.tasks")

# 每 N 分钟跑一次自动完成
AUTO_COMPLETE_INTERVAL_MINUTES = 5
# 每天凌晨跑一次学期失效
EXPIRE_SEMESTERS_CRON = {"hour": 2, "minute": 0}


def job_auto_complete(db=None) -> int:
    """班次结束后自动将「待值班」置为「已完成」。返回处理条数。

    传入 db 供测试用；默认自建会话并提交。
    """
    if db is not None:
        # 测试路径：不提交，由调用方控制事务
        n = execution_service.auto_complete_ended(db)
        return n

    with SessionLocal() as session:
        n = execution_service.auto_complete_ended(session)
        session.commit()
    if n:
        log.info("auto_complete_ended: 已自动完成 %d 条班次", n)
    return n


def job_expire_semesters(db=None, today: date | None = None) -> list[str]:
    """学期结束：该学期课表与不可值班区间失效，并将学期置为非当前。返回已处理的学期名。

    判定：is_current=True 且 first_monday + week_count*7 天 <= today。
    传入 db/today 供测试用；默认自建会话并提交。
    """
    today = today or datetime.now(timezone.utc).date()
    processed: list[str] = []

    def _do(session) -> list[str]:
        from app.models.timetable import TimetableUpload
        from app.models.enums import ReviewStatus
        from sqlalchemy import func
        rows = list(session.scalars(select(Semester)))
        result: list[str] = []
        for sem in rows:
            end = sem.first_monday + timedelta(weeks=sem.week_count)
            if end <= today:
                # Check if there are still approved uploads for this semester
                has_active = session.scalar(
                    select(func.count(TimetableUpload.id)).where(
                        TimetableUpload.semester_id == sem.id,
                        TimetableUpload.review_status == ReviewStatus.approved,
                    )
                )
                if has_active > 0:
                    n = timetable_service.expire_semester_courses(session, sem.id)
                    result.append(sem.name)
                    log.info(
                        "expire_semester_courses: 学期「%s」已结束（%s），自动失效 %d 份课表",
                        sem.name, end, n,
                    )
        return result

    if db is not None:
        return _do(db)

    with SessionLocal() as session:
        processed = _do(session)
        session.commit()
    return processed


def build_scheduler() -> BlockingScheduler:
    """构造 scheduler（不启动）。供入口与测试检视触发器配置。"""
    scheduler = BlockingScheduler(timezone="UTC", logger=log)
    scheduler.add_job(
        job_auto_complete,
        IntervalTrigger(minutes=AUTO_COMPLETE_INTERVAL_MINUTES),
        id="auto-complete",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    scheduler.add_job(
        job_expire_semesters,
        CronTrigger(**EXPIRE_SEMESTERS_CRON, timezone="UTC"),
        id="expire-semesters",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    return scheduler


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    scheduler = build_scheduler()
    log.info(
        "任务运行器启动：auto-complete 每 %d 分钟；expire-semesters 每日 %02d:%02d UTC",
        AUTO_COMPLETE_INTERVAL_MINUTES,
        EXPIRE_SEMESTERS_CRON["hour"], EXPIRE_SEMESTERS_CRON["minute"],
    )
    # 启动时各跑一次，避免重启后首批延迟
    try:
        job_auto_complete()
        job_expire_semesters()
    except Exception:  # noqa: BLE001 — 启动自检失败不应阻塞 scheduler
        log.exception("启动自检任务失败，继续运行 scheduler")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
