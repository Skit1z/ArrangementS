import { type Board, parsePosKey, type SlotView, type WeekPerson } from "./types";

export type DropVerdict = "ok" | "preference" | "hard" | "overlap";

export interface VerdictResult {
  verdict: DropVerdict;
  reasons: string[];
}

function overlaps(a: SlotView, b: SlotView): boolean {
  return (
    new Date(a.slot_start_at) < new Date(b.slot_end_at) &&
    new Date(b.slot_start_at) < new Date(a.slot_end_at)
  );
}

/**
 * 前端拖拽反馈（仅提示，服务端为最终判定方）：
 * - overlap（深红）：该人在本周已排到时间重叠的岗位，绝对禁止
 * - hard（红）：课程/不可值班/场地等强制约束，可强制安排但需填原因
 * - preference（黄）：未参与自动排班等软提示
 */
export function evaluateDrop(
  personId: string,
  targetSlot: SlotView,
  targetKey: string,
  board: Board,
  slotsById: Record<string, SlotView>,
  person: WeekPerson | undefined,
  /** 移动来源位置：该位置会被腾空，判定重叠时必须忽略，否则合法移动会被误判 */
  fromKey?: string | null,
): VerdictResult {
  const reasons: string[] = [];

  if (fromKey) {
    const { slotId: fromSlotId } = parsePosKey(fromKey);
    if (fromSlotId === targetSlot.id) {
      return { verdict: "overlap", reasons: ["已在该班次中"] };
    }
  }

  for (const [key, occupant] of Object.entries(board)) {
    if (!occupant || occupant.person_id !== personId) continue;
    if (key === targetKey || key === fromKey) continue;
    const { slotId } = parsePosKey(key);
    if (slotId === targetSlot.id) {
      return { verdict: "overlap", reasons: ["已在该班次的其他位置"] };
    }
    const other = slotsById[slotId];
    if (other && overlaps(other, targetSlot)) {
      return { verdict: "overlap", reasons: ["与已排班次时间重叠（绝对禁止）"] };
    }
  }

  if (person?.unavailable_slot_ids.includes(targetSlot.id)) {
    reasons.push("课程 / 不可值班 / 场地等强制约束冲突");
    return { verdict: "hard", reasons };
  }

  if (person && !person.in_scheduling_pool) {
    reasons.push("未参与自动排班");
    return { verdict: "preference", reasons };
  }

  return { verdict: "ok", reasons };
}

export const VERDICT_COLOR: Record<DropVerdict, string> = {
  ok: "#52c41a",
  preference: "#faad14",
  hard: "#ff4d4f",
  overlap: "#a8071a",
};
