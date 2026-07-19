import { useDraggable } from "@dnd-kit/core";

interface Props {
  id: string; // 拖拽标识：drawer:<personId> 或 pos:<positionKey>
  personId: string;
  label: string;
  color?: string;
  compact?: boolean;
}

export default function PersonChip({ id, personId, label, color, compact }: Props) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id,
    data: { personId },
  });

  let bg = "#f0f5ff";
  let border = "1px solid #adc6ff";
  let borderLeft = "4px solid #2f54eb";
  let textColor = "#1d39c4";

  if (color === "red") {
    bg = "#fff1f0";
    border = "1px solid #ffa39e";
    borderLeft = "4px solid #f5222d";
    textColor = "#cf1322";
  } else if (color === "orange") {
    bg = "#fff7e6";
    border = "1px solid #ffd591";
    borderLeft = "4px solid #fa8c16";
    textColor = "#d46b08";
  } else if (color === "green") {
    bg = "#f6ffed";
    border = "1px solid #b7eb8f";
    borderLeft = "4px solid #52c41a";
    textColor = "#389e0d";
  }

  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      style={{
        opacity: isDragging ? 0.4 : 1,
        cursor: "grab",
        touchAction: "none",
        display: compact ? "block" : "inline-block",
        width: compact ? "100%" : "auto",
        background: bg,
        border,
        borderLeft,
        color: textColor,
        padding: compact ? "4px 8px" : "5px 12px",
        borderRadius: "4px",
        fontSize: compact ? "12px" : "13px",
        fontWeight: "bold",
        userSelect: "none",
        boxSizing: "border-box",
      }}
    >
      {label}
    </div>
  );
}
