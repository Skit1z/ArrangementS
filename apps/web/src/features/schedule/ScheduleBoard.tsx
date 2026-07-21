import {
  DndContext,
  DragOverlay,
  PointerSensor,
  closestCenter,
  pointerWithin,
  rectIntersection,
  useSensor,
  useSensors,
  type CollisionDetection,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { App, Button, Card, Col, DatePicker, Divider, Empty, Form, Input, InputNumber, Modal, Popconfirm, Row, Space, Spin, Switch, Table, Tag, Tabs } from "antd";
import dayjs from "dayjs";
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { errorMessage } from "@/api/client";

import PersonDrawer from "./PersonDrawer";
import SlotCell from "./SlotCell";
import { evaluateDrop, type DropVerdict } from "./conflicts";
import {
  type Board,
  type Conflict,
  type DraftOperation,
  diffBoard,
  parsePosKey,
  type PositionKey,
  type SlotView,
  type WeekPerson,
  type WeekView,
} from "./types";
import { adminApi, TASK_STATUS_COLOR, TASK_STATUS_LABEL, type Venue } from "@/features/admin/api";

const MAX_HISTORY = 50;

export function compactBoard(board: Board): Board {
  const next: Board = {};
  const groups: Record<string, { person_id: string; person_name: string }[]> = {};

  Object.keys(board).forEach((key) => {
    const occupant = board[key];
    if (occupant) {
      const slotId = key.split(":")[0];
      if (!groups[slotId]) groups[slotId] = [];
      groups[slotId].push(occupant);
    }
  });

  Object.keys(groups).forEach((slotId) => {
    groups[slotId].forEach((occupant, idx) => {
      next[`${slotId}:${idx}`] = occupant;
    });
  });

  return next;
}

/**
 * 人员标签很小、位置槽较窄，纯矩形相交常常判不到目标。
 * 优先用指针位置命中，落空再退回矩形相交 / 最近中心。
 */
const collisionDetection: CollisionDetection = (args) => {
  const pointerHits = pointerWithin(args);
  if (pointerHits.length > 0) return pointerHits;
  const rectHits = rectIntersection(args);
  return rectHits.length > 0 ? rectHits : closestCenter(args);
};

interface Props {
  week: WeekView;
  people: WeekPerson[];
  venues: Venue[];
  baseline: Board;
  board: Board;
  setBoard: (b: Board) => void;
  conflicts: Conflict[];
  onSave: (ops: DraftOperation[]) => void;
  saving: boolean;
  checkingConflicts?: boolean;
  activeVenueId: string | null;
  setActiveVenueId: (id: string | null) => void;
}

export default function ScheduleBoard({
  week,
  people,
  venues,
  baseline,
  board,
  setBoard,
  conflicts,
  onSave,
  saving,
  checkingConflicts,
  activeVenueId,
  setActiveVenueId,
}: Props) {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }));

  const [activePerson, setActivePerson] = useState<{ id: string; name: string; from: string } | null>(null);
  const [activeVerdict, setActiveVerdict] = useState<{ key: string; verdict: DropVerdict } | null>(null);
  const [focusSlotId, setFocusSlotId] = useState<string | null>(null);
  const [forcedReasons, setForcedReasons] = useState<Record<PositionKey, string>>({});
  const [drawerCollapsed, setDrawerCollapsed] = useState(false);
  const [drawerWidth, setDrawerWidth] = useState(260);
  const [isResizing, setIsResizing] = useState(false);
  const [drawerPos, setDrawerPos] = useState({ x: window.innerWidth - 290, y: 120 });
  const [isDraggingPos, setIsDraggingPos] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });

  const startResize = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  };

  const startDrag = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsDraggingPos(true);
    setDragOffset({
      x: e.clientX - drawerPos.x,
      y: e.clientY - drawerPos.y,
    });
  };

  useEffect(() => {
    if (!isResizing) return;
    const handleMouseMove = (e: MouseEvent) => {
      const newWidth = window.innerWidth - e.clientX - 16;
      if (newWidth > 200 && newWidth < 600) {
        setDrawerWidth(newWidth);
      }
    };
    const handleMouseUp = () => {
      setIsResizing(false);
    };
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isResizing]);

  useEffect(() => {
    if (!isDraggingPos) return;
    const handleMouseMove = (e: MouseEvent) => {
      setDrawerPos({
        x: e.clientX - dragOffset.x,
        y: e.clientY - dragOffset.y
      });
    };
    const handleMouseUp = () => {
      setIsDraggingPos(false);
    };
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDraggingPos, dragOffset]);

  // 撤销 / 重做栈（至少 50 步）
  const history = useRef<Board[]>([]);
  const future = useRef<Board[]>([]);
  const [, forceRerender] = useState(0);

  const slotsById = useMemo(
    () => Object.fromEntries(week.slots.map((s) => [s.id, s])) as Record<string, SlotView>,
    [week.slots],
  );
  const peopleById = useMemo(
    () => Object.fromEntries(people.map((p) => [p.person_id, p])),
    [people],
  );
  const conflictKeys = useMemo(
    () =>
      new Set(
        conflicts
          .filter((c) => c.position_index >= 0)
          .map((c) => `${c.slot_id}:${c.position_index}`),
      ),
    [conflicts],
  );

  const slotsByVenue = useMemo(() => {
    const groups: Record<string, SlotView[]> = {};
    for (const s of week.slots) {
      if (!groups[s.venue_id]) groups[s.venue_id] = [];
      groups[s.venue_id].push(s);
    }
    return groups;
  }, [week.slots]);

  const activeVenues = useMemo(() => {
    return venues;
  }, [venues]);



  const days = useMemo(() => {
    const start = dayjs(week.week_start);
    return Array.from({ length: 7 }, (_, i) => start.add(i, "day"));
  }, [week.week_start]);

  function pushHistory(next: Board) {
    const compacted = compactBoard(next);
    history.current.push(board);
    if (history.current.length > MAX_HISTORY) history.current.shift();
    future.current = [];
    setBoard(compacted);
    forceRerender((v) => v + 1);
  }

  function undo() {
    const prev = history.current.pop();
    if (!prev) return;
    future.current.push(board);
    setBoard(prev);
    forceRerender((v) => v + 1);
  }

  function redo() {
    const next = future.current.pop();
    if (!next) return;
    history.current.push(board);
    setBoard(next);
    forceRerender((v) => v + 1);
  }

  function clearAll() {
    Modal.confirm({
      title: "确定清空当前所有排班吗？",
      content: "该操作将清空本周草稿中的所有人员安排，保存后生效。",
      okText: "确定清空",
      okType: "danger",
      cancelText: "取消",
      onOk: () => {
        const next = { ...board };
        for (const key of Object.keys(next)) {
          const slot = slotsById[parsePosKey(key).slotId];
          if (!slot?.is_locked) next[key] = null;
        }
        pushHistory(next);
      },
    });
  }

  function onDragStart(e: DragStartEvent) {
    const personId = e.active.data.current?.personId as string;
    const person = peopleById[personId];
    setActivePerson({
      id: personId,
      name: person?.full_name ?? "",
      from: String(e.active.id),
    });
  }

  function onDragOver(e: DragOverEvent) {
    const overId = String(e.over?.id ?? "");
    if (!activePerson || !overId.startsWith("pos:")) {
      setActiveVerdict(null);
      setFocusSlotId(null);
      return;
    }
    const key = overId.slice(4);
    const { slotId } = parsePosKey(key);
    const slot = slotsById[slotId];
    if (!slot) return;
    if (slot.is_locked) {
      message.warning("该岗位已锁定，请先解锁再调整");
      return;
    }
    setFocusSlotId(slotId);
    const fromKey = activePerson.from.startsWith("pos:") ? activePerson.from.slice(4) : null;
    const { verdict } = evaluateDrop(
      activePerson.id,
      slot,
      key,
      board,
      slotsById,
      peopleById[activePerson.id],
      fromKey,
    );
    setActiveVerdict({ key, verdict });
  }

  function onDragEnd(e: DragEndEvent) {
    const person = activePerson;
    setActivePerson(null);
    setActiveVerdict(null);
    setFocusSlotId(null);
    if (!person) return;

    const overId = String(e.over?.id ?? "");
    const fromKey = person.from.startsWith("pos:") ? person.from.slice(4) : null;

    // 拖到空白区域 / 拖回抽屉 / 释放在非槽位区域 -> 从原岗位删除
    if (!overId.startsWith("pos:")) {
      if (fromKey) {
        const next = { ...board, [fromKey]: null };
        pushHistory(next);
        message.info(`已移除 ${person.name} 在该班次的安排`);
      }
      return;
    }

    const targetKey = overId.slice(4);
    if (targetKey === fromKey) return;
    const { slotId } = parsePosKey(targetKey);
    const slot = slotsById[slotId];
    if (!slot) return;

    const { verdict, reasons } = evaluateDrop(
      person.id,
      slot,
      targetKey,
      board,
      slotsById,
      peopleById[person.id],
      fromKey,
    );

    if (verdict === "overlap") {
      message.error(`不能安排：${reasons.join("；")}`);
      return; // 时间重叠绝对禁止
    }

    const applyMove = (reason?: string) => {
      const next: Board = { ...board };
      const displaced = board[targetKey] ?? null;

      if (fromKey) next[fromKey] = null; // 位置间移动，先腾空来源
      next[targetKey] = { person_id: person.id, person_name: person.name };

      // 目标已有人：优先对调，避免有人被静默移出排班
      if (displaced && displaced.person_id !== person.id) {
        if (fromKey) {
          const fromSlot = slotsById[parsePosKey(fromKey).slotId];
          const swapCheck = evaluateDrop(
            displaced.person_id,
            fromSlot,
            fromKey,
            next,
            slotsById,
            peopleById[displaced.person_id],
            targetKey,
          );
          if (swapCheck.verdict === "ok" || swapCheck.verdict === "preference") {
            next[fromKey] = displaced; // 两人对调
          } else {
            message.warning(`${displaced.person_name} 无法与 ${person.name} 对调（${swapCheck.reasons.join("；")}），已移出该岗位`);
          }
        } else {
          message.warning(`${displaced.person_name} 已被移出该岗位`);
        }
      }

      if (reason) setForcedReasons((m) => ({ ...m, [targetKey]: reason }));
      pushHistory(next);

      // 检测相邻连续班次，提示一键连排
      const consecSlot = week.slots.find((s) => {
        if (s.id === slot.id || s.venue_id !== slot.venue_id) return false;
        if (!dayjs(s.slot_start_at).isSame(dayjs(slot.slot_start_at), "day")) return false;
        const gap = Math.abs(dayjs(s.slot_start_at).diff(dayjs(slot.slot_end_at), "minute"));
        const gapBack = Math.abs(dayjs(slot.slot_start_at).diff(dayjs(s.slot_end_at), "minute"));
        return gap <= 30 || gapBack <= 30;
      });

      if (consecSlot) {
        let openIdx = -1;
        for (let i = 0; i < consecSlot.required_people; i++) {
          if (!next[`${consecSlot.id}:${i}`]) {
            openIdx = i;
            break;
          }
        }
        if (openIdx >= 0) {
          const openKey = `${consecSlot.id}:${openIdx}`;
          const check = evaluateDrop(
            person.id,
            consecSlot,
            openKey,
            next,
            slotsById,
            peopleById[person.id],
            null,
          );
          if (check.verdict === "ok" || check.verdict === "preference") {
            Modal.confirm({
              title: "顺便安排连续班次？",
              content: `${person.name} 已安排于 ${dayjs(slot.slot_start_at).format("HH:mm")}–${dayjs(slot.slot_end_at).format("HH:mm")}。相邻班次 (${dayjs(consecSlot.slot_start_at).format("HH:mm")}–${dayjs(consecSlot.slot_end_at).format("HH:mm")}) 尚有空缺，是否顺便连排两班？`,
              okText: "顺便连排",
              cancelText: "暂不",
              onOk: () => {
                const doubleNext = {
                  ...next,
                  [openKey]: { person_id: person.id, person_name: person.name },
                };
                pushHistory(doubleNext);
                message.success(`已顺便将 ${person.name} 安排至相邻连班 (${dayjs(consecSlot.slot_start_at).format("HH:mm")}–${dayjs(consecSlot.slot_end_at).format("HH:mm")})`);
              },
            });
          }
        }
      }
    };

    if (verdict === "hard") {
      let reason = "";
      Modal.confirm({
        title: "存在强制约束冲突",
        content: (
          <div>
            <p>{reasons.join("；")}</p>
            <p>如确需安排，请填写强制安排原因（将写入审计日志）：</p>
            <Input.TextArea rows={2} onChange={(ev) => (reason = ev.target.value)} />
          </div>
        ),
        okText: "强制安排",
        cancelText: "取消",
        onOk: () => {
          if (!reason.trim()) {
            message.error("必须填写强制安排原因");
            return Promise.reject(new Error("no reason"));
          }
          applyMove(reason.trim());
          return Promise.resolve();
        },
      });
      return;
    }

    if (verdict === "preference") message.warning(reasons.join("；"));
    applyMove();
  }

  const ops = diffBoard(baseline, board, forcedReasons);
  const realConflicts = useMemo(() => conflicts.filter((c) => c.kind !== "vacancy"), [conflicts]);
  const dirty = ops.length > 0;

  const marginRightValue = 0;

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={collisionDetection}
      onDragStart={onDragStart}
      onDragOver={onDragOver}
      onDragEnd={onDragEnd}
    >
      <Space style={{ marginBottom: 12 }} wrap>
        <Button onClick={undo} disabled={history.current.length === 0}>
          撤销
        </Button>
        <Button onClick={redo} disabled={future.current.length === 0}>
          重做
        </Button>
        {week.status === "draft" && (
          <Button danger onClick={clearAll}>
            清空所有
          </Button>
        )}
        <Button
          type="primary"
          disabled={!dirty}
          loading={saving}
          onClick={() => onSave(ops)}
        >
          保存草稿{dirty ? `（${ops.length} 项变更）` : ""}
        </Button>
        <Tag color={dirty ? "orange" : "green"}>{dirty ? "有未保存修改" : "已保存"}</Tag>
        {checkingConflicts ? (
          <Tag color="blue">
            <Spin size="small" style={{ marginRight: 6 }} />
            正在检测冲突...
          </Tag>
        ) : (
          realConflicts.length > 0 && <Tag color="red">冲突 {realConflicts.length}</Tag>
        )}
      </Space>

      <Row gutter={12} style={{ position: "relative" }}>
        <Col
          flex="auto"
          style={{
            marginRight: marginRightValue,
          }}
        >
          <Tabs
            activeKey={activeVenueId || undefined}
            onChange={(key) => setActiveVenueId(key)}
            style={{ marginBottom: 16 }}
            items={activeVenues.map((venue) => {
              const vSlots = slotsByVenue[venue.id] || [];
              const times = Array.from(new Set(vSlots.map(s => dayjs(s.slot_start_at).format("HH:mm")))).sort();
              return {
                key: venue.id,
                label: venue.name,
                children: (
                  <>
                    {times.length === 0 ? (
                      <Card size="small" bordered={false} style={{ marginBottom: 12 }}>
                        <Empty description="该场地本周暂无排班任务，您可以点击上方“新增临时值班”来添加" style={{ padding: "40px 0" }} />
                      </Card>
                    ) : (
                      <Card size="small" bordered={false} style={{ marginBottom: 12 }}>
                        <div style={{ overflowX: "auto" }}>
                          <table style={{ borderCollapse: "separate", borderSpacing: 4, minWidth: 1100 }}>
                            <thead>
                              <tr>
                                <th style={{ width: 56 }} />
                                {days.map((d) => (
                                  <th key={d.format()} style={{ fontSize: 12, fontWeight: 500, minWidth: 140 }}>
                                    {d.format("MM-DD")} 周{"日一二三四五六"[d.day()]}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {times.map((t) => (
                                <tr key={t}>
                                  <td style={{ fontSize: 11, color: "#888" }}>{t}</td>
                                  {days.map((d) => {
                                    const slot = vSlots.find(
                                      (s) =>
                                        dayjs(s.slot_start_at).format("YYYY-MM-DD") === d.format("YYYY-MM-DD") &&
                                        dayjs(s.slot_start_at).format("HH:mm") === t,
                                    );
                                    return (
                                      <td key={d.format() + t} style={{ verticalAlign: "top" }}>
                                        {slot ? (
                                          <SlotCell
                                            slot={slot}
                                            board={board}
                                            activeVerdict={activeVerdict}
                                            conflictKeys={conflictKeys}
                                          />
                                        ) : (
                                          <div style={{ fontSize: 11, color: "#ccc", textAlign: "center" }}>—</div>
                                        )}
                                      </td>
                                    );
                                  })}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </Card>
                    )}
                    {venue.venue_type === "event_based" && (
                      <VenueTasksSection
                        venue={venue}
                        weekStart={week.week_start}
                        weekEnd={week.week_end}
                        onTaskChanged={() => {
                          qc.invalidateQueries({ queryKey: ["week", week.week_start] });
                        }}
                      />
                    )}
                  </>
                )
              };
            })}
          />
        </Col>
        
        {/* Floating Draggable & Resizable Person Drawer Wrapper */}
        <div
          style={{
            position: "fixed",
            left: drawerPos.x,
            top: drawerPos.y,
            width: drawerWidth,
            height: drawerCollapsed ? 44 : 520,
            zIndex: 1000,
            transition: isResizing || isDraggingPos ? "none" : "left 0.2s, top 0.2s, width 0.2s, height 0.2s",
            overflow: "visible",
          }}
        >
          {!drawerCollapsed && (
            <div
              style={{
                position: "absolute",
                left: -3,
                top: 0,
                bottom: 0,
                width: 6,
                cursor: "col-resize",
                zIndex: 1020,
                background: isResizing ? "#1890ff" : "transparent",
                transition: "background 0.2s",
              }}
              onMouseDown={startResize}
            />
          )}

          <PersonDrawer
            week={week}
            board={board}
            people={people}
            focusSlotId={focusSlotId}
            collapsed={drawerCollapsed}
            onToggleCollapse={() => setDrawerCollapsed(!drawerCollapsed)}
            startDrag={startDrag}
          />
        </div>
      </Row>

      <DragOverlay>
        {activePerson ? <Tag color="blue">{activePerson.name}</Tag> : null}
      </DragOverlay>
    </DndContext>
  );
}

function VenueTasksSection({
  venue,
  weekStart,
  weekEnd,
  onTaskChanged,
}: {
  venue: Venue;
  weekStart: string;
  weekEnd: string;
  onTaskChanged: () => void;
}) {
  const { message } = App.useApp();
  const [creating, setCreating] = useState(false);
  const [form] = Form.useForm();

  const tasksQ = useQuery({
    queryKey: ["admin", "venue-tasks", venue.id, weekStart],
    queryFn: () =>
      adminApi.tasks.list({
        venue_id: venue.id,
        from: weekStart,
        to: weekEnd,
        include_cancelled: true,
      }),
  });

  const createM = useMutation({
    mutationFn: async (values: any) => {
      const range: [dayjs.Dayjs, dayjs.Dayjs] = values.booking_range;
      return await adminApi.tasks.create({
        venue_id: venue.id,
        title: values.title,
        booking_start_at: range[0].toISOString(),
        booking_end_at: range[1].toISOString(),
        prep_minutes: values.prep_minutes,
        cleanup_minutes: values.cleanup_minutes,
        required_people: values.required_people,
        is_temporary: values.is_temporary,
        organization: values.organization,
        contact_name: values.contact_name,
        contact_phone: values.contact_phone,
        requirements: values.requirements,
        notes: values.notes,
      });
    },
    onSuccess: () => {
      message.success("任务已创建");
      setCreating(false);
      form.resetFields();
      tasksQ.refetch();
      onTaskChanged();
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const cancelM = useMutation({
    mutationFn: (id: string) => adminApi.tasks.cancel(id),
    onSuccess: () => {
      message.success("任务已取消");
      tasksQ.refetch();
      onTaskChanged();
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const openCreate = () => {
    form.resetFields();
    form.setFieldsValue({
      title: "",
      booking_range: undefined,
      prep_minutes: venue.default_prep_minutes ?? 30,
      cleanup_minutes: venue.default_cleanup_minutes ?? 30,
      required_people: venue.default_required_people ?? 2,
      is_temporary: false,
    });
    setCreating(true);
  };

  const submit = async () => {
    const values = await form.validateFields();
    createM.mutate(values);
  };

  const columns = [
    { title: "任务标题", dataIndex: "title" },
    {
      title: "预约时间",
      key: "booking_time",
      render: (_: any, r: any) =>
        `${dayjs(r.booking_start_at).format("MM-DD HH:mm")}–${dayjs(r.booking_end_at).format("HH:mm")}`,
    },
    { title: "需求人数", dataIndex: "required_people", width: 90 },
    {
      title: "状态",
      dataIndex: "status",
      width: 90,
      render: (s: string) => (
        <Tag color={TASK_STATUS_COLOR[s as keyof typeof TASK_STATUS_COLOR] ?? "default"}>
          {TASK_STATUS_LABEL[s as keyof typeof TASK_STATUS_LABEL] ?? s}
        </Tag>
      ),
    },
    {
      title: "操作",
      width: 100,
      render: (_: any, r: any) => (
        r.status !== "cancelled" && r.status !== "completed" && (
          <Popconfirm title="确认取消该任务？" onConfirm={() => cancelM.mutate(r.id)}>
            <Button size="small" danger>
              取消
            </Button>
          </Popconfirm>
        )
      ),
    },
  ];

  return (
    <div style={{ marginTop: 24 }}>
      <Divider orientation="left" style={{ margin: "0 0 16px 0" }}>
        <Space>
          <span style={{ fontSize: "16px", fontWeight: 600 }}>场地任务管理 ({venue.name})</span>
          <Button type="primary" size="small" onClick={openCreate}>
            新建任务
          </Button>
        </Space>
      </Divider>
      
      <Table
        size="small"
        rowKey="id"
        loading={tasksQ.isLoading}
        dataSource={tasksQ.data ?? []}
        columns={columns}
        pagination={false}
        locale={{ emptyText: "本周该场地暂无任务记录" }}
      />

      {creating && (
        <Modal
          title={`新建场地任务 - ${venue.name}`}
          open
          onOk={submit}
          onCancel={() => setCreating(false)}
          confirmLoading={createM.isPending}
          destroyOnClose
          width={600}
        >
          <Form form={form} layout="vertical">
            <Form.Item name="title" label="标题" rules={[{ required: true }]}>
              <Input placeholder="如：重要会议技术保障" />
            </Form.Item>
            <Form.Item
              name="booking_range"
              label="预约起止时间"
              rules={[{ required: true, message: "请选择预约时间" }]}
            >
              <DatePicker.RangePicker showTime format="YYYY-MM-DD HH:mm" style={{ width: "100%" }} />
            </Form.Item>
            <Space wrap>
              <Form.Item name="prep_minutes" label="提前到岗(分钟)" rules={[{ required: true }]}>
                <InputNumber min={0} />
              </Form.Item>
              <Form.Item name="cleanup_minutes" label="收尾(分钟)" rules={[{ required: true }]}>
                <InputNumber min={0} />
              </Form.Item>
              <Form.Item name="required_people" label="需求人数" rules={[{ required: true }]}>
                <InputNumber min={1} />
              </Form.Item>
              <Form.Item name="is_temporary" label="临时任务" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Space>
            <Form.Item name="organization" label="主办方">
              <Input />
            </Form.Item>
            <Space wrap>
              <Form.Item name="contact_name" label="联系人">
                <Input />
              </Form.Item>
              <Form.Item name="contact_phone" label="联系电话">
                <Input />
              </Form.Item>
            </Space>
            <Form.Item name="requirements" label="特殊要求">
              <Input.TextArea rows={2} />
            </Form.Item>
            <Form.Item name="notes" label="备注">
              <Input.TextArea rows={2} />
            </Form.Item>
          </Form>
        </Modal>
      )}
    </div>
  );
}
