import { useDroppable } from "@dnd-kit/core";
import { LockOutlined } from "@ant-design/icons";
import dayjs from "dayjs";

import PersonChip from "./PersonChip";
import { VERDICT_COLOR, type DropVerdict } from "./conflicts";
import { type Board, posKey, type SlotView } from "./types";

interface Props {
  slot: SlotView;
  board: Board;
  activeVerdict: { key: string; verdict: DropVerdict } | null;
  conflictKeys: Set<string>;
}

function Position({
  slot,
  index,
  board,
  activeVerdict,
  conflictKeys,
}: Props & { index: number }) {
  const key = posKey(slot.id, index);
  const occupant = board[key] ?? null;
  const { setNodeRef, isOver } = useDroppable({ id: `pos:${key}`, data: { positionKey: key } });

  const verdict = activeVerdict?.key === key ? activeVerdict.verdict : null;
  const hasConflict = conflictKeys.has(key);

  let background = occupant ? "#f6ffed" : "#fafafa";
  let border = occupant ? "1px dashed #b7eb8f" : "1px dashed #d9d9d9";
  if (verdict) {
    background = `${VERDICT_COLOR[verdict]}22`;
    border = `2px solid ${VERDICT_COLOR[verdict]}`;
  } else if (hasConflict) {
    border = "2px solid #ff4d4f";
  }

  return (
    <div
      ref={setNodeRef}
      style={{
        minHeight: 30,
        borderRadius: 4,
        padding: 2,
        marginBottom: 3,
        background,
        border,
        outline: isOver && !verdict ? "1px solid #1677ff" : "none",
      }}
    >
      {occupant ? (
        <PersonChip
          id={`pos:${key}`}
          personId={occupant.person_id}
          label={occupant.person_name}
          color={hasConflict ? "red" : "green"}
          compact
        />
      ) : (
        <span style={{ fontSize: 12, fontWeight: 600, color: "#ff4d4f", paddingLeft: 4 }}>空缺</span>
      )}
    </div>
  );
}

export default function SlotCell(props: Props) {
  const { slot } = props;
  const occupiedIndices = Object.keys(props.board)
    .filter((k) => k.startsWith(slot.id + ":") && props.board[k] !== null)
    .map((k) => parseInt(k.split(":")[1], 10));
  const maxIndex = occupiedIndices.length > 0 ? Math.max(...occupiedIndices) : -1;
  const renderCount = Math.max(slot.required_people, maxIndex + 2);
  const filled = occupiedIndices.length;

  return (
    <div style={{ border: "1px solid #f0f0f0", borderRadius: 6, padding: 6, background: "#fff" }}>
      <div style={{ fontSize: 11, color: "#888", marginBottom: 4, display: "flex", justifyContent: "space-between" }}>
        <span>
          {dayjs(slot.slot_start_at).format("HH:mm")}-{dayjs(slot.slot_end_at).format("HH:mm")}
        </span>
        <span>
          {slot.is_locked && <LockOutlined style={{ marginRight: 4 }} />}
          {filled}/{slot.required_people}
        </span>
      </div>
      {Array.from({ length: renderCount }).map((_, i) => (
        <Position key={i} {...props} index={i} />
      ))}
    </div>
  );
}
