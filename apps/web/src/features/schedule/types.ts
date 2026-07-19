export interface AssignmentView {
  id: string;
  person_id: string | null;
  person_name: string | null;
  position_index: number;
  plan_status: string;
  execution_status: string;
  credited_minutes: number;
}

export interface SlotView {
  id: string;
  venue_id: string;
  source_type: "fixed_shift" | "venue_task";
  slot_start_at: string;
  slot_end_at: string;
  required_people: number;
  month_key: string;
  status: string;
  is_locked: boolean;
  assignments: AssignmentView[];
}

export interface WeekView {
  plan_id: string;
  week_start: string;
  week_end: string;
  status: string;
  revision: number;
  version: number;
  week_label: string;
  slots: SlotView[];
}

export interface WeekPerson {
  person_id: string;
  full_name: string;
  class_name: string;
  student_no: string;
  month_balance_minutes: number;
  week_shift_count: number;
  in_scheduling_pool: boolean;
  unavailable_slot_ids: string[];
}

export interface Conflict {
  slot_id: string;
  position_index: number;
  person_id: string | null;
  kind: "time_overlap" | "hard_constraint" | "vacancy";
  message: string;
}

/** 棋盘：位置键 "slotId:posIdx" -> 人员（null 表示空缺） */
export type PositionKey = string;
export interface Occupant {
  person_id: string;
  person_name: string;
}
export type Board = Record<PositionKey, Occupant | null>;

export function posKey(slotId: string, index: number): PositionKey {
  return `${slotId}:${index}`;
}

export function parsePosKey(key: PositionKey): { slotId: string; index: number } {
  const i = key.lastIndexOf(":");
  return { slotId: key.slice(0, i), index: Number(key.slice(i + 1)) };
}

export function boardFromWeek(week: WeekView): Board {
  const board: Board = {};
  for (const slot of week.slots) {
    for (let i = 0; i < slot.required_people; i++) {
      const a = slot.assignments.find((x) => x.position_index === i);
      board[posKey(slot.id, i)] =
        a && a.person_id ? { person_id: a.person_id, person_name: a.person_name ?? "" } : null;
    }
  }
  return board;
}

/** 用棋盘与服务端基线做差分，得出需要提交的操作 */
export interface DraftOperation {
  op: "assign" | "unassign";
  slot_id: string;
  position_index: number;
  person_id?: string;
  forced?: boolean;
  forced_reason?: string;
}

export function diffBoard(
  baseline: Board,
  current: Board,
  forcedReasons: Record<PositionKey, string>,
): DraftOperation[] {
  const unassigns: DraftOperation[] = [];
  const assigns: DraftOperation[] = [];
  for (const key of Object.keys(current)) {
    const before = baseline[key] ?? null;
    const after = current[key] ?? null;
    if (before?.person_id === after?.person_id) continue;
    const { slotId, index } = parsePosKey(key);
    if (after === null) {
      unassigns.push({ op: "unassign", slot_id: slotId, position_index: index });
    } else {
      const reason = forcedReasons[key];
      assigns.push({
        op: "assign",
        slot_id: slotId,
        position_index: index,
        person_id: after.person_id,
        ...(reason ? { forced: true, forced_reason: reason } : {}),
      });
    }
  }
  // 先腾空再占位：移动某人到与其原班次重叠的岗位时，若先执行 assign，
  // 服务端仍会看到其旧分配而误判时间重叠，从而拒绝合法移动。
  return [...unassigns, ...assigns];
}
