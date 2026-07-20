import { useDroppable } from "@dnd-kit/core";
import { DownOutlined, UpOutlined } from "@ant-design/icons";
import { Button, Empty, Input, Select, Space, Tooltip } from "antd";
import { useMemo, useState } from "react";

import PersonChip from "./PersonChip";
import type { WeekPerson } from "./types";

interface Props {
  people: WeekPerson[];
  /** 当前拖拽悬停的岗位（用于按该岗位可用性过滤） */
  focusSlotId: string | null;
  collapsed: boolean;
  onToggleCollapse: () => void;
  startDrag: (e: React.MouseEvent) => void;
}

function hours(minutes: number) {
  return (minutes / 60).toFixed(1);
}

export default function PersonDrawer({
  people,
  focusSlotId,
  collapsed,
  onToggleCollapse,
  startDrag,
}: Props) {
  const [keyword, setKeyword] = useState("");
  const [className, setClassName] = useState<string | undefined>();
  const [onlyAvailable, setOnlyAvailable] = useState(false);
  const [onlyUnscheduled, setOnlyUnscheduled] = useState(false);

  // 拖回抽屉 = 取消该位置的安排
  const { setNodeRef, isOver } = useDroppable({ id: "drawer" });

  const classes = useMemo(
    () => Array.from(new Set(people.map((p) => p.class_name))).sort(),
    [people],
  );

  const filtered = useMemo(() => {
    return people.filter((p) => {
      if (keyword && !p.full_name.includes(keyword) && !p.student_no.includes(keyword)) return false;
      if (className && p.class_name !== className) return false;
      if (onlyUnscheduled && p.week_shift_count > 0) return false;
      if (onlyAvailable && focusSlotId && p.unavailable_slot_ids.includes(focusSlotId)) return false;
      return true;
    });
  }, [people, keyword, className, onlyAvailable, onlyUnscheduled, focusSlotId]);

  return (
    <div
      ref={setNodeRef as never}
      style={{
        background: "#fff",
        border: "1px solid #e8e8e8",
        borderRadius: 8,
        boxShadow: "0 4px 16px rgba(0,0,0,0.12)",
        outline: isOver ? "2px solid #1677ff" : "none",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        height: "100%",
      }}
    >
      {/* 标题栏：作为抓手按住拖动 + 向上折叠按钮 */}
      <div
        className="drag-handle"
        onMouseDown={startDrag}
        style={{
          padding: "8px 12px",
          background: "#fafafa",
          borderBottom: collapsed ? "none" : "1px solid #f0f0f0",
          cursor: "grab",
          userSelect: "none",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <span style={{ fontWeight: 600, fontSize: 13, color: "#333" }}>
          👥 人员库 ({people.length}人)
        </span>
        <Button
          type="text"
          size="small"
          icon={collapsed ? <DownOutlined /> : <UpOutlined />}
          onClick={(e) => {
            e.stopPropagation();
            onToggleCollapse();
          }}
          aria-label={collapsed ? "展开人员库" : "折叠人员库"}
        />
      </div>

      {!collapsed && (
        <div style={{ flex: 1, overflowY: "auto", padding: "10px 12px" }}>
          <Space direction="vertical" style={{ width: "100%", marginBottom: 8 }} size={6}>
            <Input.Search placeholder="姓名 / 学号" allowClear onSearch={setKeyword} size="small" />
            <Select
              allowClear
              size="small"
              placeholder="班级"
              style={{ width: "100%" }}
              value={className}
              onChange={setClassName}
              options={classes.map((c) => ({ value: c, label: c }))}
            />
            <Space size={4} wrap>
              <a onClick={() => setOnlyAvailable((v) => !v)} style={{ fontSize: 12 }}>
                {onlyAvailable ? "✓ " : ""}当前岗位可用
              </a>
              <a onClick={() => setOnlyUnscheduled((v) => !v)} style={{ fontSize: 12 }}>
                {onlyUnscheduled ? "✓ " : ""}本周未排
              </a>
            </Space>
            <div style={{ fontSize: 11, color: "#999" }}>拖动人员到班次；拖回此处取消安排</div>
          </Space>

          {filtered.length === 0 && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="无匹配人员" />}
          {filtered.map((p) => {
            const unavailable = focusSlotId ? p.unavailable_slot_ids.includes(focusSlotId) : false;
            return (
              <div key={p.person_id} style={{ marginBottom: 4 }}>
                <Tooltip
                  title={`${p.class_name} · 本周 ${p.week_shift_count} 班${
                    unavailable ? " · 该岗位不可用" : ""
                  }${p.in_scheduling_pool ? "" : " · 未参与自动排班"}`}
                >
                  <span>
                    <PersonChip
                      id={`drawer:${p.person_id}`}
                      personId={p.person_id}
                      label={`${p.full_name} ${hours(p.month_balance_minutes)}h`}
                      color={unavailable ? "red" : p.in_scheduling_pool ? "blue" : "orange"}
                    />
                  </span>
                </Tooltip>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
