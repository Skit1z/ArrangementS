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
import { App, Button, Card, Col, Input, Modal, Row, Space, Tag } from "antd";
import dayjs from "dayjs";
import { useMemo, useRef, useState } from "react";

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
import { type Venue } from "@/features/admin/api";

const MAX_HISTORY = 50;

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
}: Props) {
  const { message } = App.useApp();
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }));

  const [activePerson, setActivePerson] = useState<{ id: string; name: string; from: string } | null>(null);
  const [activeVerdict, setActiveVerdict] = useState<{ key: string; verdict: DropVerdict } | null>(null);
  const [focusSlotId, setFocusSlotId] = useState<string | null>(null);
  const [forcedReasons, setForcedReasons] = useState<Record<PositionKey, string>>({});

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

  const fixedSlots = week.slots.filter((s) => s.source_type === "fixed_shift");
  const taskSlots = week.slots.filter((s) => s.source_type === "venue_task");

  const fixedVenues = useMemo(() => {
    const venueIds = new Set(fixedSlots.map(s => s.venue_id));
    return venues.filter(v => venueIds.has(v.id));
  }, [fixedSlots, venues]);

  const days = useMemo(() => {
    const start = dayjs(week.week_start);
    return Array.from({ length: 7 }, (_, i) => start.add(i, "day"));
  }, [week.week_start]);

  function pushHistory(next: Board) {
    history.current.push(board);
    if (history.current.length > MAX_HISTORY) history.current.shift();
    future.current = [];
    setBoard(next);
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

    // 拖回抽屉 -> 取消安排
    if (overId === "drawer") {
      if (!fromKey) return;
      const next = { ...board, [fromKey]: null };
      pushHistory(next);
      return;
    }
    if (!overId.startsWith("pos:")) return;

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
  const dirty = ops.length > 0;

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
        <Button
          type="primary"
          disabled={!dirty}
          loading={saving}
          onClick={() => onSave(ops)}
        >
          保存草稿{dirty ? `（${ops.length} 项变更）` : ""}
        </Button>
        <Tag color={dirty ? "orange" : "green"}>{dirty ? "有未保存修改" : "已保存"}</Tag>
        {conflicts.length > 0 && <Tag color="red">冲突 {conflicts.length}</Tag>}
      </Space>

      <Row gutter={12}>
        <Col flex="auto">
          {fixedVenues.map((venue) => {
            const vSlots = fixedSlots.filter(s => s.venue_id === venue.id);
            const times = Array.from(new Set(vSlots.map(s => dayjs(s.slot_start_at).format("HH:mm")))).sort();
            return (
              <Card key={venue.id} size="small" title={venue.name} style={{ marginBottom: 12 }}>
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
            );
          })}

          {taskSlots.length > 0 && (
            <Card size="small" title="场地任务（蓝厅 / 图书馆报告厅）">
              <Row gutter={[8, 8]}>
                {taskSlots.map((s) => (
                  <Col key={s.id} span={6}>
                    <div style={{ fontSize: 11, color: "#888" }}>
                      {dayjs(s.slot_start_at).format("MM-DD")}
                    </div>
                    <SlotCell
                      slot={s}
                      board={board}
                      activeVerdict={activeVerdict}
                      conflictKeys={conflictKeys}
                    />
                  </Col>
                ))}
              </Row>
            </Card>
          )}
        </Col>
        <Col flex="260px">
          <div style={{ position: "sticky", top: 16 }}>
            <PersonDrawer people={people} focusSlotId={focusSlotId} />
          </div>
        </Col>
      </Row>

      <DragOverlay>
        {activePerson ? <Tag color="blue">{activePerson.name}</Tag> : null}
      </DragOverlay>
    </DndContext>
  );
}
