import { useDroppable } from "@dnd-kit/core";
import { DownOutlined, UpOutlined } from "@ant-design/icons";
import { Button, Empty, Input, Select, Space, Tooltip } from "antd";
import { useMemo, useState } from "react";

import dayjs from "dayjs";
import PersonChip from "./PersonChip";
import type { Board, WeekPerson, WeekView } from "./types";

interface Props {
  week?: WeekView;
  board?: Board;
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
  week,
  board,
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

  const consecutivePersonIds = useMemo(() => {
    if (!focusSlotId || !week || !board) return new Set<string>();
    const slot = week.slots.find((s) => s.id === focusSlotId);
    if (!slot) return new Set<string>();

    const slotStart = dayjs(slot.slot_start_at);
    const slotEnd = dayjs(slot.slot_end_at);

    // 寻找同一场地、同一天、时间衔接（间隔 <= 30 min）的相邻班次
    const adjSlots = week.slots.filter((s) => {
      if (s.id === slot.id || s.venue_id !== slot.venue_id) return false;
      if (!dayjs(s.slot_start_at).isSame(slotStart, "day")) return false;
      const gap1 = Math.abs(dayjs(s.slot_end_at).diff(slotStart, "minute"));
      const gap2 = Math.abs(dayjs(s.slot_start_at).diff(slotEnd, "minute"));
      return gap1 <= 30 || gap2 <= 30;
    });

    const set = new Set<string>();
    for (const adj of adjSlots) {
      for (let i = 0; i < adj.required_people; i++) {
        const occ = board[`${adj.id}:${i}`];
        if (occ?.person_id) {
          set.add(occ.person_id);
        }
      }
    }
    return set;
  }, [focusSlotId, week, board]);

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
      {/* 标题栏：作为抓手按住拖动 + 高亮显眼的折叠/展开按钮 */}
      <div
        className="drag-handle"
        onMouseDown={startDrag}
        style={{
          height: 44,
          padding: "0 14px",
          background: "linear-gradient(135deg, #1F497D 0%, #1677ff 100%)",
          color: "#fff",
          borderBottom: collapsed ? "none" : "1px solid #102A45",
          cursor: "grab",
          userSelect: "none",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          boxShadow: "0 2px 6px rgba(0,0,0,0.15)",
          whiteSpace: "nowrap",
          overflow: "hidden",
          boxSizing: "border-box",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, whiteSpace: "nowrap", overflow: "hidden" }}>
          <span style={{ fontWeight: 700, fontSize: 14, color: "#fff", letterSpacing: 0.5, whiteSpace: "nowrap" }}>
            人员库
          </span>
          <span
            style={{
              background: "rgba(255, 255, 255, 0.25)",
              color: "#fff",
              fontSize: 12,
              fontWeight: 600,
              padding: "1px 8px",
              borderRadius: 10,
              whiteSpace: "nowrap",
            }}
          >
            {people.length} 人
          </span>
        </div>

        <Button
          size="small"
          onClick={(e) => {
            e.stopPropagation();
            onToggleCollapse();
          }}
          style={
            collapsed
              ? {
                  background: "#fff",
                  color: "#1677ff",
                  fontWeight: 700,
                  borderColor: "#fff",
                  borderRadius: 14,
                  boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
                  whiteSpace: "nowrap",
                  flexShrink: 0,
                }
              : {
                  background: "rgba(255, 255, 255, 0.2)",
                  color: "#fff",
                  borderColor: "rgba(255, 255, 255, 0.4)",
                  fontWeight: 600,
                  borderRadius: 14,
                  whiteSpace: "nowrap",
                  flexShrink: 0,
                }
          }
          icon={collapsed ? <DownOutlined /> : <UpOutlined />}
        >
          {collapsed ? "展开人员库" : "向上折叠"}
        </Button>
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

          {filtered.length === 0 ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="无匹配人员" />
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(105px, 1fr))", gap: 6 }}>
              {filtered.map((p) => {
                const unavailable = focusSlotId ? p.unavailable_slot_ids.includes(focusSlotId) : false;
                const isConsecutive = consecutivePersonIds.has(p.person_id);
                return (
                  <Tooltip
                    key={p.person_id}
                    title={`${p.class_name} · 本周 ${p.week_shift_count} 班${
                      isConsecutive ? " · ⚡相邻班次已排（推荐连班）" : ""
                    }${unavailable ? " · 该岗位不可用" : ""}${
                      p.in_scheduling_pool ? "" : " · 未参与自动排班"
                    }`}
                  >
                    <div>
                      <PersonChip
                        id={`drawer:${p.person_id}`}
                        personId={p.person_id}
                        label={`${p.full_name}${isConsecutive ? " ⚡连班" : ""} ${hours(p.month_balance_minutes)}h`}
                        color={unavailable ? "red" : isConsecutive ? "green" : p.in_scheduling_pool ? "blue" : "orange"}
                        compact
                      />
                    </div>
                  </Tooltip>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
