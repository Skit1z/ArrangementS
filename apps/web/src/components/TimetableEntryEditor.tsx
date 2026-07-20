import { App, Button, Form, Input, InputNumber, Modal, Select } from "antd";
import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { useState } from "react";

import type { ParsedEntry } from "@/features/me/api";

const WEEKDAYS = [
  { value: 1, label: "周一" },
  { value: 2, label: "周二" },
  { value: 3, label: "周三" },
  { value: 4, label: "周四" },
  { value: 5, label: "周五" },
  { value: 6, label: "周六" },
  { value: 7, label: "周日" },
];

const PERIOD_BLOCKS = [
  { label: "1-2 节", start: 1, end: 2, time: "08:00-09:50" },
  { label: "3-4 节", start: 3, end: 4, time: "10:05-12:10" },
  { label: "5-6 节", start: 5, end: 6, time: "14:00-15:50" },
  { label: "7-8 节", start: 7, end: 8, time: "16:05-17:55" },
  { label: "9-10 节", start: 9, end: 10, time: "19:00-20:50" },
];

const CARD_PALETTE = [
  { bg: "#e6f4ff", border: "#91caff", color: "#0958d9", tagBg: "#bae0ff" },
  { bg: "#f6ffed", border: "#b7eb8f", color: "#389e0d", tagBg: "#d9f7be" },
  { bg: "#fff7e6", border: "#ffd591", color: "#d46b08", tagBg: "#ffe7ba" },
  { bg: "#f9f0ff", border: "#d3ade6", color: "#531dab", tagBg: "#efdbff" },
  { bg: "#e6fffb", border: "#87e8de", color: "#08979c", tagBg: "#b5f5ec" },
];

interface Props {
  value: ParsedEntry[];
  onChange: (entries: ParsedEntry[]) => void;
  maxHeight?: number;
}

export function TimetableEntryEditor({ value, onChange }: Props) {
  const { modal } = App.useApp();

  // 编辑/新增弹窗状态
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editingModalOpen, setEditingModalOpen] = useState(false);
  const [editForm] = Form.useForm<ParsedEntry>();

  const update = (index: number, patch: Partial<ParsedEntry>) => {
    onChange(value.map((entry, i) => (i === index ? { ...entry, ...patch } : entry)));
  };

  const openEditModal = (index: number) => {
    const entry = value[index];
    editForm.setFieldsValue({
      weekday: entry.weekday,
      period_start: entry.period_start,
      period_end: entry.period_end,
      week_expr: entry.week_expr,
      location_code: entry.location_code ?? "",
      course_name: entry.course_name ?? "",
    });
    setEditingIndex(index);
    setEditingModalOpen(true);
  };

  const openAddModal = (defaultWeekday = 1, defaultStart = 1, defaultEnd = 2) => {
    editForm.setFieldsValue({
      weekday: defaultWeekday,
      period_start: defaultStart,
      period_end: defaultEnd,
      week_expr: "1-20周",
      location_code: "",
      course_name: "",
    });
    setEditingIndex(-1);
    setEditingModalOpen(true);
  };

  const saveModalForm = async () => {
    const vals = await editForm.validateFields();
    const cleanEntry: ParsedEntry = {
      weekday: vals.weekday,
      period_start: vals.period_start,
      period_end: vals.period_end,
      week_expr: vals.week_expr.trim() || "1-20周",
      location_code: vals.location_code?.trim() || null,
      course_name: vals.course_name?.trim() || null,
    };

    if (editingIndex === -1) {
      onChange([...value, cleanEntry]);
    } else if (editingIndex !== null && editingIndex >= 0) {
      update(editingIndex, cleanEntry);
    }
    setEditingModalOpen(false);
  };

  const deleteEntry = (index: number) => {
    onChange(value.filter((_, i) => i !== index));
  };

  // 检查是否有11节及以后的极端班次，有则动态扩展网格行
  const maxPeriod = Math.max(...value.map((e) => e.period_end), 10);
  const displayBlocks = [...PERIOD_BLOCKS];
  if (maxPeriod > 10) {
    displayBlocks.push({ label: "11-12 节", start: 11, end: 12, time: "晚间时段" });
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <span style={{ fontWeight: 600, fontSize: 14, color: "#333" }}>📅 课程表可视化预览</span>
        <Button size="small" type="primary" icon={<PlusOutlined />} onClick={() => openAddModal()}>
          添加课程
        </Button>
      </div>

      <div style={{ overflowX: "auto", border: "1px solid #f0f0f0", borderRadius: 8, background: "#fafafa" }}>
        <table style={{ borderCollapse: "collapse", width: "100%", minWidth: 720, tableLayout: "fixed" }}>
          <thead>
            <tr style={{ background: "#f5f5f5", borderBottom: "1px solid #e8e8e8" }}>
              <th style={{ padding: "8px 4px", width: 75, textAlign: "center", fontSize: 12, color: "#666" }}>
                节次 / 时间
              </th>
              {WEEKDAYS.map((wd) => (
                <th
                  key={wd.value}
                  style={{
                    padding: "8px 4px",
                    textAlign: "center",
                    fontSize: 13,
                    fontWeight: 600,
                    color: "#333",
                    borderLeft: "1px solid #e8e8e8",
                  }}
                >
                  {wd.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {displayBlocks.map((block) => (
              <tr key={block.label} style={{ borderBottom: "1px solid #f0f0f0" }}>
                <td
                  style={{
                    padding: "6px 2px",
                    textAlign: "center",
                    background: "#fafafa",
                    fontSize: 12,
                    borderRight: "1px solid #e8e8e8",
                  }}
                >
                  <div style={{ fontWeight: 600, color: "#444" }}>{block.label}</div>
                  <div style={{ fontSize: 10, color: "#999" }}>{block.time}</div>
                </td>
                {WEEKDAYS.map((wd) => {
                  const entriesInCell = value
                    .map((entry, originalIdx) => ({ entry, originalIdx }))
                    .filter(
                      ({ entry }) =>
                        entry.weekday === wd.value &&
                        !(entry.period_end < block.start || entry.period_start > block.end)
                    );

                  return (
                    <td
                      key={wd.value}
                      style={{
                        padding: 4,
                        verticalAlign: "top",
                        height: 68,
                        background: "#fff",
                        borderLeft: "1px solid #f0f0f0",
                        position: "relative",
                      }}
                    >
                      {entriesInCell.length === 0 ? (
                        <div
                          onClick={() => openAddModal(wd.value, block.start, block.end)}
                          style={{
                            height: "100%",
                            minHeight: 58,
                            borderRadius: 6,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            cursor: "pointer",
                            color: "transparent",
                            transition: "all 0.2s",
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.background = "#f0f7ff";
                            e.currentTarget.style.color = "#1677ff";
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.background = "transparent";
                            e.currentTarget.style.color = "transparent";
                          }}
                        >
                          <PlusOutlined style={{ fontSize: 14 }} />
                        </div>
                      ) : (
                        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                          {entriesInCell.map(({ entry, originalIdx }) => {
                            const style = CARD_PALETTE[originalIdx % CARD_PALETTE.length];
                            return (
                              <div
                                key={originalIdx}
                                style={{
                                  background: style.bg,
                                  border: `1px solid ${style.border}`,
                                  borderLeft: `3px solid ${style.color}`,
                                  borderRadius: 6,
                                  padding: "4px 6px",
                                  fontSize: 11,
                                  cursor: "pointer",
                                  position: "relative",
                                  boxShadow: "0 1px 2px rgba(0,0,0,0.03)",
                                }}
                                onClick={() => openEditModal(originalIdx)}
                              >
                                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                  <span style={{ fontWeight: 600, color: style.color, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "80%" }}>
                                    {entry.course_name || "课程占用"}
                                  </span>
                                  <DeleteOutlined
                                    style={{ color: "#ff4d4f", fontSize: 12 }}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      modal.confirm({
                                        title: "确认删除该课程时段？",
                                        okText: "删除",
                                        cancelText: "取消",
                                        okButtonProps: { danger: true },
                                        onOk: () => deleteEntry(originalIdx),
                                      });
                                    }}
                                  />
                                </div>
                                <div style={{ color: "#555", marginTop: 2, fontSize: 10 }}>
                                  🗓️ {entry.week_expr}
                                </div>
                                {entry.location_code && (
                                  <div style={{ color: "#777", fontSize: 10 }}>
                                    📍 {entry.location_code}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 课程详情编辑/新增 Modal */}
      <Modal
        title={editingIndex === -1 ? "添加课程时段" : "编辑课程时段"}
        open={editingModalOpen}
        onOk={saveModalForm}
        onCancel={() => setEditingModalOpen(false)}
        okText="保存"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={editForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="weekday" label="星期" rules={[{ required: true }]}>
            <Select options={WEEKDAYS} style={{ width: "100%" }} />
          </Form.Item>
          <div style={{ display: "flex", gap: 12 }}>
            <Form.Item name="period_start" label="开始节次" rules={[{ required: true }]} style={{ flex: 1 }}>
              <InputNumber min={1} max={20} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="period_end" label="结束节次" rules={[{ required: true }]} style={{ flex: 1 }}>
              <InputNumber min={1} max={20} style={{ width: "100%" }} />
            </Form.Item>
          </div>
          <Form.Item name="week_expr" label="周次表达" rules={[{ required: true, message: "请输入周次表达" }]}>
            <Input placeholder="如 1-16周 或 1-16单周" />
          </Form.Item>
          <Form.Item name="location_code" label="上课地点/教室代码 (可选)">
            <Input placeholder="如 B608 或 02-101" />
          </Form.Item>
          <Form.Item name="course_name" label="课程名称 (可选)">
            <Input placeholder="如 高等数学" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
