import { useDraggable } from "@dnd-kit/core";
import { Tag } from "antd";

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

  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      style={{
        opacity: isDragging ? 0.4 : 1,
        cursor: "grab",
        touchAction: "none",
        display: "inline-block",
      }}
    >
      <Tag color={color} style={{ margin: 2, fontSize: compact ? 12 : 13 }}>
        {label}
      </Tag>
    </div>
  );
}
