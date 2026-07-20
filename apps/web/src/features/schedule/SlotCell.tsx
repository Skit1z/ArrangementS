import { useDroppable, useDndContext } from "@dnd-kit/core";
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
  const { setNodeRef, isOver } = useDroppable({
    id: `pos:${key}`,
    data: { positionKey: key },
  });

  const verdict = activeVerdict?.key === key ? activeVerdict.verdict : null;
  const hasConflict = conflictKeys.has(key);

  if (occupant) {
    return (
      <div
        ref={setNodeRef}
        style={{
          minHeight: 30,
          borderRadius: 4,
          marginBottom: 3,
          boxSizing: "border-box",
          outline: isOver && !verdict ? "1px solid #1677ff" : "none",
        }}
      >
        <PersonChip
          id={`pos:${key}`}
          personId={occupant.person_id}
          label={occupant.person_name}
          color={hasConflict ? "red" : "blue"}
          compact
        />
      </div>
    );
  }

  let bg = "#fafafa";
  let border = "1px dashed #d9d9d9";
  let borderLeft = "4px dashed #d9d9d9";
  let textColor = "#8c8c8c";
  let text = "+ 拖拽至此添加";
  let fontWeight = "normal";

  if (index < slot.required_people) {
    bg = "#fff1f0";
    border = "1px dashed #ffa39e";
    borderLeft = "4px solid #f5222d";
    textColor = "#f5222d";
    text = "空缺";
    fontWeight = "bold";
  }

  if (verdict) {
    bg = `${VERDICT_COLOR[verdict]}22`;
    border = `2px solid ${VERDICT_COLOR[verdict]}`;
    borderLeft = `4px solid ${VERDICT_COLOR[verdict]}`;
  }

  return (
    <div
      ref={setNodeRef}
      style={{
        minHeight: 30,
        borderRadius: 4,
        marginBottom: 3,
        background: bg,
        border,
        borderLeft,
        color: textColor,
        display: "flex",
        alignItems: "center",
        paddingLeft: 8,
        fontSize: 12,
        fontWeight,
        boxSizing: "border-box",
        outline: isOver && !verdict ? "1px solid #1677ff" : "none",
      }}
    >
      {text}
    </div>
  );
}

export default function SlotCell(props: Props) {
  const { slot } = props;
  const { active } = useDndContext();
  const isDragging = !!active;

  // 整理当前 Slot 内的所有在岗人员（按索引顺序取非空人员）
  const slotOccupants = Object.keys(props.board)
    .filter((k) => k.startsWith(slot.id + ":") && props.board[k] !== null)
    .sort((a, b) => parseInt(a.split(":")[1], 10) - parseInt(b.split(":")[1], 10))
    .map((k) => props.board[k]!);

  // 构造无缝紧凑排列的 effectiveBoard，确保空缺始终居于已分配人员下方
  const effectiveBoard: Board = { ...props.board };
  Object.keys(props.board)
    .filter((k) => k.startsWith(slot.id + ":"))
    .forEach((k) => {
      delete effectiveBoard[k];
    });
  slotOccupants.forEach((occupant, idx) => {
    effectiveBoard[posKey(slot.id, idx)] = occupant;
  });

  const filled = slotOccupants.length;
  // 未满员时显示所需名额数；满员时平时绝不主动展示多余灰框，仅在拖拽中准备放置时展示 +1 个拖投点
  const renderCount = filled < slot.required_people
    ? slot.required_people
    : filled + (isDragging ? 1 : 0);

  const effectiveProps = { ...props, board: effectiveBoard };

  return (
    <div style={{ border: "1px solid #f0f0f0", borderRadius: 6, padding: 6, background: "#fff" }}>
      <div style={{ fontSize: 11, color: "#888", marginBottom: 4, display: "flex", justifyContent: "space-between" }}>
        <span>
          {dayjs(slot.slot_start_at).format("HH:mm")}-{dayjs(slot.slot_end_at).format("HH:mm")}
        </span>
        <span>
          {filled}/{slot.required_people}
        </span>
      </div>
      {Array.from({ length: renderCount }).map((_, i) => (
        <Position key={i} {...effectiveProps} index={i} />
      ))}
    </div>
  );
}
