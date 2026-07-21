"""OR-Tools 排班求解器测试（方案 19.3）。"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.scheduling.solver import Position, SolverInput, solve


def pos(
    pid: str, slot: str, start_h: int, dur_h: int = 2, credited: int = 120, month="2026-03"
) -> Position:
    start = datetime(2026, 3, 2, start_h, 0)
    return Position(
        id=pid,
        slot_id=slot,
        month_key=month,
        credited_minutes=credited,
        venue_id="HL",
        start_at=start,
        end_at=start + timedelta(hours=dur_h),
    )


def all_available(persons, positions):
    return {(p, pos.id): True for p in persons for pos in positions}


def test_weekday_two_people_distinct():
    persons = ["a", "b", "c"]
    positions = [pos("s1-0", "s1", 8), pos("s1-1", "s1", 8)]  # 同班两个岗位
    result = solve(
        SolverInput(
            positions=positions, persons=persons, available=all_available(persons, positions)
        )
    )
    assigned = [result.assignments["s1-0"], result.assignments["s1-1"]]
    assert None not in assigned
    assert assigned[0] != assigned[1]  # 不同人


def test_course_conflict_excluded():
    persons = ["a", "b"]
    positions = [pos("s1-0", "s1", 8)]
    avail = all_available(persons, positions)
    avail[("a", "s1-0")] = False  # a 有课冲突
    result = solve(SolverInput(positions=positions, persons=persons, available=avail))
    assert result.assignments["s1-0"] == "b"


def test_time_overlap_excluded():
    persons = ["a"]
    # 两个时间重叠的岗位，只有一个人 → 一个必然空缺
    positions = [pos("p1", "s1", 8, dur_h=2), pos("p2", "s2", 9, dur_h=2)]
    result = solve(
        SolverInput(
            positions=positions, persons=persons, available=all_available(persons, positions)
        )
    )
    filled = [v for v in result.assignments.values() if v == "a"]
    assert len(filled) == 1  # a 只能在一个重叠岗位
    assert len(result.vacancies) == 1


def test_weekly_limit():
    persons = ["a", "b"]
    positions = [pos("p1", "s1", 8), pos("p2", "s2", 12), pos("p3", "s3", 16)]  # 互不重叠
    result = solve(
        SolverInput(
            positions=positions,
            persons=persons,
            available=all_available(persons, positions),
            weekly_limit={"a": 1, "b": 1},
        )
    )
    # 每人最多 1 班 → 3 个岗位只能填 2 个
    assert len(result.vacancies) == 1


def test_forbidden_pair_same_slot():
    persons = ["a", "b", "c"]
    positions = [pos("s1-0", "s1", 8), pos("s1-1", "s1", 8)]
    result = solve(
        SolverInput(
            positions=positions,
            persons=persons,
            available=all_available(persons, positions),
            forbidden_pairs=[("a", "b")],
        )
    )
    filled = {result.assignments["s1-0"], result.assignments["s1-1"]}
    assert not ({"a", "b"} <= filled)  # a、b 不同时出现


def test_vacancy_when_infeasible():
    persons = ["a"]
    positions = [pos("s1-0", "s1", 8), pos("s1-1", "s1", 8)]  # 同班需 2 人但只有 1 人
    result = solve(
        SolverInput(
            positions=positions, persons=persons, available=all_available(persons, positions)
        )
    )
    assert len(result.vacancies) == 1  # 一个空缺，绝不违反硬约束


def test_fairness_balances_hours():
    persons = ["a", "b"]
    # 4 个互不重叠岗位，历史：a 已有 240，b 有 0 → 应多分给 b
    positions = [pos(f"p{i}", f"s{i}", 8 + i * 2) for i in range(4)]  # 8,10,12,14
    result = solve(
        SolverInput(
            positions=positions,
            persons=persons,
            available=all_available(persons, positions),
            history_minutes={"a": 240, "b": 0},
        )
    )
    counts = {"a": 0, "b": 0}
    for v in result.assignments.values():
        if v:
            counts[v] += 1
    assert counts["b"] >= counts["a"]  # b 分得更多以趋于均衡


def test_reproducible_with_seed():
    persons = ["a", "b", "c", "d"]
    positions = [pos(f"p{i}", f"s{i}", 8 + i * 2) for i in range(3)]
    inp = lambda: SolverInput(
        positions=positions, persons=persons, available=all_available(persons, positions), seed=123
    )  # noqa: E731
    r1 = solve(inp())
    r2 = solve(inp())
    assert r1.assignments == r2.assignments


def test_locked_assignment_respected():
    persons = ["a", "b"]
    positions = [pos("s1-0", "s1", 8), pos("s1-1", "s1", 8)]
    result = solve(
        SolverInput(
            positions=positions,
            persons=persons,
            available=all_available(persons, positions),
            locked={"s1-0": "a"},
        )
    )
    assert result.assignments["s1-0"] == "a"


def test_locked_assignment_overrides_new_unavailability():
    positions = [pos("s1-0", "s1", 8)]
    result = solve(
        SolverInput(
            positions=positions,
            persons=["a"],
            available={("a", "s1-0"): False},
            locked={"s1-0": "a"},
        )
    )
    assert result.assignments["s1-0"] == "a"


def test_locked_person_outside_pool_is_explicit_error():
    import pytest

    with pytest.raises(ValueError, match="人员不在可排班人员池"):
        solve(
            SolverInput(
                positions=[pos("s1-0", "s1", 8)],
                persons=["b"],
                available={("b", "s1-0"): True},
                locked={"s1-0": "a"},
            )
        )


# --- P1.3：多维公平目标测试 ---
def test_daily_max_per_person_enforced():
    """单人单日最多 N 班：超过会被分散到不同人。"""
    from datetime import timedelta
    from app.scheduling.solver import Position, SolverInput, solve

    start = datetime(2026, 3, 2, 8, 0)
    positions = [
        Position(
            id=f"p{i}",
            slot_id=f"s{i}",
            month_key="2026-03",
            credited_minutes=120,
            venue_id="HL",
            start_at=start + timedelta(hours=i * 3),
            end_at=start + timedelta(hours=i * 3 + 2),
        )
        for i in range(3)
    ]
    persons = ["a", "b", "c"]
    result = solve(
        SolverInput(
            positions=positions,
            persons=persons,
            available={(p, pos.id): True for p in persons for pos in positions},
            daily_max_per_person=1,
        )
    )
    counts: dict[str, int] = {}
    for pos in positions:
        chosen = result.assignments[pos.id]
        if chosen:
            counts[chosen] = counts.get(chosen, 0) + 1
    assert all(c <= 1 for c in counts.values()), counts
    assert len(counts) == 3


def test_weekend_balance_distributes_evenly():
    """周末岗位在多人间均衡分布。"""
    from datetime import timedelta
    from app.scheduling.solver import Position, SolverInput, solve

    start = datetime(2026, 3, 7, 8, 0)
    positions = [
        Position(
            id=f"p{i}",
            slot_id=f"s{i}",
            month_key="2026-03",
            credited_minutes=120,
            venue_id="HL",
            start_at=start + timedelta(days=i, hours=i * 3),
            end_at=start + timedelta(days=i, hours=i * 3 + 2),
            is_weekend=True,
        )
        for i in range(4)
    ]
    persons = ["a", "b"]
    result = solve(
        SolverInput(
            positions=positions,
            persons=persons,
            available={(p, pos.id): True for p in persons for pos in positions},
        )
    )
    counts = {"a": 0, "b": 0}
    for pos in positions:
        c = result.assignments[pos.id]
        if c:
            counts[c] += 1
    assert abs(counts["a"] - counts["b"]) <= 1, counts


def test_preference_soft_objective_preferred_person_picked():
    """个人偏好作为软目标：偏好的人会被优先选中。"""
    from datetime import timedelta
    from app.scheduling.solver import Position, SolverInput, solve

    start = datetime(2026, 3, 2, 9, 0)
    pos = Position(
        id="p0",
        slot_id="s0",
        month_key="2026-03",
        credited_minutes=120,
        venue_id="V1",
        start_at=start,
        end_at=start + timedelta(hours=2),
    )
    persons = ["a", "b"]
    result = solve(
        SolverInput(
            positions=[pos],
            persons=persons,
            available={(p, pos.id): True for p in persons},
            preferences={"a": {"V1": 10}},
        )
    )
    assert result.assignments["p0"] == "a"


def test_consecutive_shift_reward_prefers_same_person():
    """测试同场地连续两个班次在保证工时均衡的前提下优先排同一个人。"""
    from datetime import datetime
    from app.scheduling.solver import Position, SolverInput, solve

    # 第 1 天 2 连班，第 2 天 2 连班
    p1 = Position(
        id="p1",
        slot_id="s1",
        month_key="2026-03",
        credited_minutes=120,
        venue_id="HL",
        start_at=datetime(2026, 3, 2, 8, 0),
        end_at=datetime(2026, 3, 2, 10, 0),
    )
    p2 = Position(
        id="p2",
        slot_id="s2",
        month_key="2026-03",
        credited_minutes=120,
        venue_id="HL",
        start_at=datetime(2026, 3, 2, 10, 0),
        end_at=datetime(2026, 3, 2, 12, 0),
    )
    p3 = Position(
        id="p3",
        slot_id="s3",
        month_key="2026-03",
        credited_minutes=120,
        venue_id="HL",
        start_at=datetime(2026, 3, 3, 8, 0),
        end_at=datetime(2026, 3, 3, 10, 0),
    )
    p4 = Position(
        id="p4",
        slot_id="s4",
        month_key="2026-03",
        credited_minutes=120,
        venue_id="HL",
        start_at=datetime(2026, 3, 3, 10, 0),
        end_at=datetime(2026, 3, 3, 12, 0),
    )
    persons = ["a", "b"]
    positions = [p1, p2, p3, p4]
    result = solve(
        SolverInput(
            positions=positions,
            persons=persons,
            available={(p, pos.id): True for p in persons for pos in positions},
        )
    )
    # 在 4 个岗位中，p1 与 p2 同人，p3 与 p4 同人（且工时各 240min 保持均衡）
    assert result.assignments["p1"] == result.assignments["p2"]
    assert result.assignments["p3"] == result.assignments["p4"]
