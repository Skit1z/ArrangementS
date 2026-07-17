import { describe, expect, it } from "vitest";

import { evaluateDrop } from "./conflicts";
import { type Board, diffBoard, posKey, type SlotView, type WeekPerson } from "./types";

function slot(id: string, startHour: number, endHour: number): SlotView {
  const d = (h: number) => `2026-03-02T${String(h).padStart(2, "0")}:00:00`;
  return {
    id,
    venue_id: "v1",
    source_type: "fixed_shift",
    slot_start_at: d(startHour),
    slot_end_at: d(endHour),
    required_people: 2,
    month_key: "2026-03",
    status: "open",
    is_locked: false,
    assignments: [],
  };
}

const A = slot("A", 8, 10);
const B = slot("B", 9, 11); // 与 A 重叠
const C = slot("C", 12, 14); // 与 A 不重叠
const slotsById = { A, B, C };

const person: WeekPerson = {
  person_id: "p1",
  full_name: "张三",
  class_name: "一班",
  student_no: "1",
  month_balance_minutes: 0,
  week_shift_count: 0,
  in_scheduling_pool: true,
  unavailable_slot_ids: [],
};

describe("evaluateDrop", () => {
  it("同一人排到时间重叠的岗位 -> overlap（绝对禁止）", () => {
    const board: Board = { [posKey("A", 0)]: { person_id: "p1", person_name: "张三" } };
    const r = evaluateDrop("p1", B, posKey("B", 0), board, slotsById, person);
    expect(r.verdict).toBe("overlap");
  });

  it("同一人排到同一班次的另一个位置 -> overlap", () => {
    const board: Board = { [posKey("A", 0)]: { person_id: "p1", person_name: "张三" } };
    const r = evaluateDrop("p1", A, posKey("A", 1), board, slotsById, person);
    expect(r.verdict).toBe("overlap");
  });

  it("从重叠岗位移动过去 -> 允许（原位置会被腾空，不应误判）", () => {
    const board: Board = { [posKey("A", 0)]: { person_id: "p1", person_name: "张三" } };
    const r = evaluateDrop("p1", B, posKey("B", 0), board, slotsById, person, posKey("A", 0));
    expect(r.verdict).toBe("ok");
  });

  it("不重叠岗位 -> ok", () => {
    const board: Board = { [posKey("A", 0)]: { person_id: "p1", person_name: "张三" } };
    const r = evaluateDrop("p1", C, posKey("C", 0), board, slotsById, person);
    expect(r.verdict).toBe("ok");
  });

  it("强制约束冲突 -> hard", () => {
    const p = { ...person, unavailable_slot_ids: ["C"] };
    const r = evaluateDrop("p1", C, posKey("C", 0), {}, slotsById, p);
    expect(r.verdict).toBe("hard");
  });

  it("未参与自动排班 -> preference（仅提示）", () => {
    const p = { ...person, in_scheduling_pool: false };
    const r = evaluateDrop("p1", C, posKey("C", 0), {}, slotsById, p);
    expect(r.verdict).toBe("preference");
  });

  it("时间重叠优先于强制约束判定", () => {
    const p = { ...person, unavailable_slot_ids: ["B"] };
    const board: Board = { [posKey("A", 0)]: { person_id: "p1", person_name: "张三" } };
    const r = evaluateDrop("p1", B, posKey("B", 0), board, slotsById, p);
    expect(r.verdict).toBe("overlap");
  });
});

describe("diffBoard", () => {
  const occ = (id: string) => ({ person_id: id, person_name: id });

  it("无变化 -> 无操作", () => {
    const b: Board = { [posKey("A", 0)]: occ("p1") };
    expect(diffBoard(b, b, {})).toEqual([]);
  });

  it("移除 -> unassign", () => {
    const base: Board = { [posKey("A", 0)]: occ("p1") };
    const cur: Board = { [posKey("A", 0)]: null };
    expect(diffBoard(base, cur, {})).toEqual([
      { op: "unassign", slot_id: "A", position_index: 0 },
    ]);
  });

  it("新增 -> assign", () => {
    const base: Board = { [posKey("A", 0)]: null };
    const cur: Board = { [posKey("A", 0)]: occ("p1") };
    expect(diffBoard(base, cur, {})).toEqual([
      { op: "assign", slot_id: "A", position_index: 0, person_id: "p1" },
    ]);
  });

  it("强制安排原因随 assign 一并提交", () => {
    const base: Board = { [posKey("A", 0)]: null };
    const cur: Board = { [posKey("A", 0)]: occ("p1") };
    const ops = diffBoard(base, cur, { [posKey("A", 0)]: "人手不足" });
    expect(ops[0]).toMatchObject({ forced: true, forced_reason: "人手不足" });
  });

  it("移动时 unassign 必须排在 assign 之前（否则服务端会误判时间重叠）", () => {
    const base: Board = { [posKey("A", 0)]: occ("p1"), [posKey("B", 0)]: null };
    const cur: Board = { [posKey("A", 0)]: null, [posKey("B", 0)]: occ("p1") };
    const ops = diffBoard(base, cur, {});
    expect(ops.map((o) => o.op)).toEqual(["unassign", "assign"]);
  });

  it("即使对象键顺序相反，unassign 仍在前", () => {
    const base: Board = { [posKey("B", 0)]: null, [posKey("A", 0)]: occ("p1") };
    const cur: Board = { [posKey("B", 0)]: occ("p1"), [posKey("A", 0)]: null };
    const ops = diffBoard(base, cur, {});
    expect(ops.map((o) => o.op)).toEqual(["unassign", "assign"]);
  });
});

describe("对调语义（避免有人被静默移出）", () => {
  const occ = (id: string) => ({ person_id: id, person_name: id });

  it("被顶替者可以合法接手来源位置 -> 应可对调", () => {
    // p1 在 A0，p2 在 C0；把 p1 拖到 C0
    const board: Board = { [posKey("A", 0)]: occ("p1"), [posKey("C", 0)]: occ("p2") };
    const p2: WeekPerson = { ...person, person_id: "p2" };
    // p2 移到 A0（同时腾空 C0）应判定为 ok
    const r = evaluateDrop("p2", A, posKey("A", 0), board, slotsById, p2, posKey("C", 0));
    expect(r.verdict).toBe("ok");
  });

  it("被顶替者若与来源位置时间重叠 -> 不可对调", () => {
    // p2 同时在 B（9-11），来源 A（8-10）与之重叠
    const board: Board = {
      [posKey("A", 0)]: occ("p1"),
      [posKey("C", 0)]: occ("p2"),
      [posKey("B", 0)]: occ("p2"),
    };
    const p2: WeekPerson = { ...person, person_id: "p2" };
    const r = evaluateDrop("p2", A, posKey("A", 0), board, slotsById, p2, posKey("C", 0));
    expect(r.verdict).toBe("overlap");
  });
});
