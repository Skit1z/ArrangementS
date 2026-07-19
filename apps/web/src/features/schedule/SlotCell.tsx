import { useDroppable, useDndContext } from "@dnd-kit/core";
import { LockOutlined, UnlockOutlined } from "@ant-design/icons";
import { Button, Tooltip } from "antd";
import dayjs from "dayjs";

import PersonChip from "./PersonChip";
import { VERDICT_COLOR, type DropVerdict } from "./conflicts";
import { type Board, posKey, type SlotView } from "./types";

interface Props {
  slot: SlotView;
  board: Board;
  activeVerdict: { key: string; verdict: DropVerdict } | null;
  conflictKeys: Set<string>;
  onToggleLock: (slot: SlotView) => void;
  lockPending?: boolean;
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
    disabled: slot.is_locked,
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
          disabled={slot.is_locked}
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

  const occupiedIndices = Object.keys(props.board)
    .filter((k) => k.startsWith(slot.id + ":") && props.board[k] !== null)
    .map((k) => parseInt(k.split(":")[1], 10));
  const maxIndex = occupiedIndices.length > 0 ? Math.max(...occupiedIndices) : -1;
  const renderCount = Math.max(slot.required_people, maxIndex + (isDragging ? 2 : 1));
  const filled = occupiedIndices.length;

  return (
    <div style={{ border: "1px solid #f0f0f0", borderRadius: 6, padding: 6, background: "#fff" }}>
      <div style={{ fontSize: 11, color: "#888", marginBottom: 4, display: "flex", justifyContent: "space-between" }}>
        <span>
          {dayjs(slot.slot_start_at).format("HH:mm")}-{dayjs(slot.slot_end_at).format("HH:mm")}
        </span>
        <span>
          {filled}/{slot.required_people}
          <Tooltip title={slot.is_locked ? "解锁岗位" : filled ? "锁定当前分配" : "空缺岗位不能锁定"}>
            <Button
              type="text"
              size="small"
              aria-label={slot.is_locked ? "解锁岗位" : "锁定岗位"}
              icon={slot.is_locked ? <UnlockOutlined /> : <LockOutlined />}
              disabled={!slot.is_locked && filled === 0}
              loading={props.lockPending}
              onClick={() => props.onToggleLock(slot)}
              style={{ marginLeft: 2, width: 24, height: 22 }}
            />
          </Tooltip>
        </span>
      </div>
      {Array.from({ length: renderCount }).map((_, i) => (
        <Position key={i} {...props} index={i} />
      ))}
    </div>
  );
}
