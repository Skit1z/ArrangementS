"""场地/任务/倍率 API 冒烟测试（确认路由接线与权限）。"""

from __future__ import annotations

from tests.conftest import csrf_headers, login


def test_venue_task_multiplier_flow(client, seed_admin):
    token = login(client, "admin", "admin1234")
    h = csrf_headers(token)

    # 创建 event_based 场地
    v = client.post(
        "/api/v1/venues",
        json={
            "name": "蓝厅",
            "code": "LT",
            "venue_type": "event_based",
        },
        headers=h,
    )
    assert v.status_code == 201, v.text
    venue_id = v.json()["id"]

    # 创建任务
    t = client.post(
        "/api/v1/venue-tasks",
        json={
            "venue_id": venue_id,
            "title": "报告会",
            "booking_start_at": "2026-03-02T09:30:00",
            "booking_end_at": "2026-03-02T11:30:00",
        },
        headers=h,
    )
    assert t.status_code == 201, t.text
    task_id = t.json()["id"]
    assert t.json()["duty_start_at"].startswith("2026-03-02T09:00")

    # 工时预览
    prev = client.get(f"/api/v1/venue-tasks/{task_id}/hours-preview", headers=h)
    assert prev.status_code == 200
    assert prev.json()["credited_minutes"] >= 120

    # 倍率规则列表
    assert client.get("/api/v1/multiplier-rules", headers=h).status_code == 200


def test_list_venue_tasks(client, seed_admin):
    """GET /venue-tasks：默认排除 cancelled，支持 venue_id 过滤，附 venue_name。"""
    token = login(client, "admin", "admin1234")
    h = csrf_headers(token)

    v1 = client.post(
        "/api/v1/venues",
        json={"name": "蓝厅", "code": "LT", "venue_type": "event_based"},
        headers=h,
    ).json()
    v2 = client.post(
        "/api/v1/venues",
        json={"name": "报告厅", "code": "TSG", "venue_type": "event_based"},
        headers=h,
    ).json()

    # v1 三个任务：一个普通、一个取消；v2 一个普通
    client.post(
        "/api/v1/venue-tasks",
        json={
            "venue_id": v1["id"],
            "title": "A",
            "booking_start_at": "2026-03-02T09:00:00",
            "booking_end_at": "2026-03-02T10:00:00",
        },
        headers=h,
    ).json()
    t2 = client.post(
        "/api/v1/venue-tasks",
        json={
            "venue_id": v1["id"],
            "title": "B",
            "booking_start_at": "2026-03-02T11:00:00",
            "booking_end_at": "2026-03-02T12:00:00",
        },
        headers=h,
    ).json()
    client.post(
        "/api/v1/venue-tasks",
        json={
            "venue_id": v1["id"],
            "title": "C",
            "booking_start_at": "2026-03-03T09:00:00",
            "booking_end_at": "2026-03-03T10:00:00",
        },
        headers=h,
    )
    client.post(
        "/api/v1/venue-tasks",
        json={
            "venue_id": v2["id"],
            "title": "D",
            "booking_start_at": "2026-03-02T09:00:00",
            "booking_end_at": "2026-03-02T10:00:00",
        },
        headers=h,
    )

    # 取消 B
    client.post(f"/api/v1/venue-tasks/{t2['id']}/cancel", headers=h)

    # 默认：3 个（4 - 1 取消），含 venue_name
    rows = client.get("/api/v1/venue-tasks", headers=h).json()
    assert len(rows) == 3
    assert all("venue_name" in r for r in rows)
    titles = {r["title"] for r in rows}
    assert "B" not in titles  # 取消的不出现
    # 倒序：最早 duty_start_at 在最后
    assert rows[-1]["title"] == "A"

    # venue_id 过滤
    only_v2 = client.get(f"/api/v1/venue-tasks?venue_id={v2['id']}", headers=h).json()
    assert len(only_v2) == 1
    assert only_v2[0]["venue_name"] == "报告厅"

    # include_cancelled=True 看到全部 4 个
    all_rows = client.get("/api/v1/venue-tasks?include_cancelled=true", headers=h).json()
    assert len(all_rows) == 4


def test_multiplier_overlap_via_api(client, seed_admin):
    token = login(client, "admin", "admin1234")
    h = csrf_headers(token)
    r1 = client.post(
        "/api/v1/multiplier-rules",
        json={
            "name": "A",
            "start_time": "09:00:00",
            "end_time": "11:00:00",
            "multiplier": "2.0",
            "priority": 5,
        },
        headers=h,
    )
    assert r1.status_code == 201, r1.text
    r2 = client.post(
        "/api/v1/multiplier-rules",
        json={
            "name": "B",
            "start_time": "10:00:00",
            "end_time": "12:00:00",
            "multiplier": "2.0",
            "priority": 5,
        },
        headers=h,
    )
    assert r2.status_code == 422  # 同优先级重叠禁止


def test_holiday_sync_requires_confirm(client, seed_admin):
    token = login(client, "admin", "admin1234")
    h = csrf_headers(token)
    # 用手动导入 JSON 避免网络依赖
    resp = client.post(
        "/api/v1/special-dates/sync",
        json={
            "year": 2027,
            "data": {"days": [{"name": "元旦", "date": "2027-01-01", "isOffDay": True}]},
        },
        headers=h,
    )
    assert resp.status_code == 200
    items = resp.json()
    assert items[0]["status"] == "new"
    # 确认前列表为空
    assert client.get("/api/v1/special-dates?year=2027", headers=h).json() == []
    # 确认写入
    client.post(
        "/api/v1/special-dates/sync/confirm",
        json={"items": [{"date": "2027-01-01", "day_type": "weekend_rule", "reason": "元旦"}]},
        headers=h,
    )
    assert len(client.get("/api/v1/special-dates?year=2027", headers=h).json()) == 1


def test_audit_logs_include_username(client, seed_admin):
    """审计日志应带 actor_username，便于 admin 直接渲染。"""
    token = login(client, "admin", "admin1234")
    h = csrf_headers(token)
    # 锁定一个空月份也会写一条 statistics.lock 审计记录
    client.post("/api/v1/statistics/monthly/2026-03/lock", headers=h)

    logs = client.get("/api/v1/audit-logs", headers=h).json()
    assert len(logs) > 0
    lock_logs = [l for l in logs if l["action"] == "statistics.lock"]
    assert lock_logs and lock_logs[0]["actor_username"] == "admin"
