"""OR-Tools CP-SAT 排班求解器（方案 8）。

设计为纯数据接口，不依赖数据库，便于单元测试与复现。
强制约束绝不违反；无完全可行解时以高惩罚生成空缺草稿，绝不悄悄违反硬约束。
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime

from ortools.sat.python import cp_model

ALGORITHM_VERSION = "cpsat-v1"
VACANCY_PENALTY = 10_000_000


@dataclass
class Position:
    id: str
    slot_id: str
    month_key: str
    credited_minutes: int
    venue_id: str
    start_at: datetime
    end_at: datetime


@dataclass
class SolverInput:
    positions: list[Position]
    persons: list[str]
    available: dict[tuple[str, str], bool]  # (person, position_id) -> 可用
    weekly_limit: dict[str, int] = field(default_factory=dict)  # person -> 每周最多班次
    forbidden_pairs: list[tuple[str, str]] = field(default_factory=list)
    locked: dict[str, str] = field(default_factory=dict)  # position_id -> person（人工锁定）
    history_minutes: dict[str, int] = field(default_factory=dict)  # person -> 当月历史平衡工时
    allow_vacancy: bool = True
    seed: int = 42
    max_time_seconds: float = 30.0


@dataclass
class SolverResult:
    assignments: dict[str, str | None]  # position_id -> person 或 None(空缺)
    vacancies: list[str]
    status: str
    spread_minutes: int
    solve_time_seconds: float
    algorithm_version: str = ALGORITHM_VERSION
    seed: int = 42


def _overlapping_position_pairs(positions: list[Position]) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    ordered = sorted(range(len(positions)), key=lambda i: positions[i].start_at)
    for a in range(len(ordered)):
        i = ordered[a]
        for b in range(a + 1, len(ordered)):
            j = ordered[b]
            if positions[j].start_at >= positions[i].end_at:
                break  # 后续均不与 i 重叠（已按 start 排序）
            if positions[i].start_at < positions[j].end_at and positions[j].start_at < positions[i].end_at:
                pairs.append((i, j))
    return pairs


def solve(data: SolverInput) -> SolverResult:
    model = cp_model.CpModel()
    positions = data.positions
    persons = data.persons
    pos_index = {p.id: idx for idx, p in enumerate(positions)}

    # 决策变量 x[p, pos]
    x: dict[tuple[str, int], cp_model.IntVar] = {}
    for person in persons:
        for idx, pos in enumerate(positions):
            if data.available.get((person, pos.id), False):
                x[(person, idx)] = model.NewBoolVar(f"x_{person}_{idx}")

    # 空缺变量
    vacancy = {idx: model.NewBoolVar(f"vac_{idx}") for idx in range(len(positions))}

    # 岗位覆盖：每个岗位恰好一人，或空缺
    for idx in range(len(positions)):
        candidates = [x[(person, idx)] for person in persons if (person, idx) in x]
        if data.allow_vacancy:
            model.Add(sum(candidates) + vacancy[idx] == 1)
        else:
            model.Add(sum(candidates) == 1)
            model.Add(vacancy[idx] == 0)

    # 人工锁定
    for pos_id, person in data.locked.items():
        idx = pos_index[pos_id]
        if (person, idx) in x:
            model.Add(x[(person, idx)] == 1)

    # 时间重叠：同一人在重叠岗位最多一个
    overlaps = _overlapping_position_pairs(positions)
    for person in persons:
        for i, j in overlaps:
            vi, vj = x.get((person, i)), x.get((person, j))
            if vi is not None and vj is not None:
                model.Add(vi + vj <= 1)

    # 每周最多班次
    for person in persons:
        limit = data.weekly_limit.get(person)
        if limit is not None:
            vars_p = [x[(person, idx)] for idx in range(len(positions)) if (person, idx) in x]
            if vars_p:
                model.Add(sum(vars_p) <= limit)

    # 禁止同班：同一岗位所属 slot 内不得同时出现
    slot_positions: dict[str, list[int]] = {}
    for idx, pos in enumerate(positions):
        slot_positions.setdefault(pos.slot_id, []).append(idx)
    for a, b in data.forbidden_pairs:
        for _slot, idxs in slot_positions.items():
            for i in idxs:
                for j in idxs:
                    if i >= j:
                        continue
                    for p1, p2 in ((a, b), (b, a)):
                        v1, v2 = x.get((p1, i)), x.get((p2, j))
                        if v1 is not None and v2 is not None:
                            model.Add(v1 + v2 <= 1)

    # 预测月度平衡工时 M_p = 历史 + 本次分配
    m_terms: dict[str, list] = {person: [] for person in persons}
    for person in persons:
        for idx, pos in enumerate(positions):
            if (person, idx) in x:
                m_terms[person].append(x[(person, idx)] * pos.credited_minutes)

    total_credit = sum(p.credited_minutes for p in positions) + max(
        (v for v in data.history_minutes.values()), default=0
    )
    m_vars: dict[str, cp_model.IntVar] = {}
    for person in persons:
        mp = model.NewIntVar(0, total_credit + 1, f"M_{person}")
        model.Add(mp == data.history_minutes.get(person, 0) + sum(m_terms[person]))
        m_vars[person] = mp

    max_m = model.NewIntVar(0, total_credit + 1, "max_m")
    min_m = model.NewIntVar(0, total_credit + 1, "min_m")
    for person in persons:
        model.Add(max_m >= m_vars[person])
        model.Add(min_m <= m_vars[person])

    # 确定性微扰打破平局（可复现）
    rng = random.Random(data.seed)
    tie_terms = []
    for person in persons:
        for idx in range(len(positions)):
            if (person, idx) in x:
                tie_terms.append(x[(person, idx)] * rng.randint(0, 5))

    model.Minimize(
        VACANCY_PENALTY * sum(vacancy.values())
        + 1000 * (max_m - min_m)
        + sum(tie_terms)
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = data.max_time_seconds
    solver.parameters.random_seed = data.seed
    solver.parameters.num_search_workers = 1  # 单线程保证可复现
    status = solver.Solve(model)

    assignments: dict[str, str | None] = {}
    vacancies: list[str] = []
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for idx, pos in enumerate(positions):
            chosen = None
            for person in persons:
                if (person, idx) in x and solver.Value(x[(person, idx)]) == 1:
                    chosen = person
                    break
            assignments[pos.id] = chosen
            if chosen is None:
                vacancies.append(pos.id)
        spread = int(solver.Value(max_m) - solver.Value(min_m))
    else:
        for pos in positions:
            assignments[pos.id] = None
            vacancies.append(pos.id)
        spread = 0

    return SolverResult(
        assignments=assignments,
        vacancies=vacancies,
        status=solver.StatusName(status),
        spread_minutes=spread,
        solve_time_seconds=solver.WallTime(),
        seed=data.seed,
    )
