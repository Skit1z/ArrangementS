import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { Button, Input, InputNumber, Select, Space, Table } from "antd";

import type { ParsedEntry } from "@/features/me/api";

const WEEKDAYS = [1, 2, 3, 4, 5, 6, 7].map((value) => ({
  value,
  label: `周${"一二三四五六日"[value - 1]}`,
}));

interface Props {
  value: ParsedEntry[];
  onChange: (entries: ParsedEntry[]) => void;
  maxHeight?: number;
}

export function TimetableEntryEditor({ value, onChange, maxHeight = 320 }: Props) {
  const update = (index: number, patch: Partial<ParsedEntry>) => {
    onChange(value.map((entry, i) => (i === index ? { ...entry, ...patch } : entry)));
  };

  return (
    <>
      <Table
        size="small"
        pagination={false}
        scroll={{ x: 650, y: maxHeight }}
        rowKey="key"
        dataSource={value.map((entry, key) => ({ ...entry, key }))}
        columns={[
          {
            title: "星期",
            width: 100,
            render: (_, row) => (
              <Select
                value={row.weekday}
                options={WEEKDAYS}
                style={{ width: 82 }}
                onChange={(weekday) => update(row.key, { weekday })}
              />
            ),
          },
          {
            title: "节次",
            width: 170,
            render: (_, row) => (
              <Space.Compact>
                <InputNumber min={1} max={20} value={row.period_start}
                  onChange={(period_start) => update(row.key, { period_start: period_start ?? 1 })} />
                <Input disabled value="至" style={{ width: 38, textAlign: "center" }} />
                <InputNumber min={1} max={20} value={row.period_end}
                  onChange={(period_end) => update(row.key, { period_end: period_end ?? 1 })} />
              </Space.Compact>
            ),
          },
          {
            title: "周次",
            width: 145,
            render: (_, row) => (
              <Input value={row.week_expr} placeholder="如 1-16周"
                onChange={(event) => update(row.key, { week_expr: event.target.value })} />
            ),
          },
          {
            title: "场地",
            width: 130,
            render: (_, row) => (
              <Input value={row.location_code ?? ""} placeholder="可留空"
                onChange={(event) => update(row.key, { location_code: event.target.value || null })} />
            ),
          },
          {
            title: "操作",
            width: 65,
            fixed: "right" as const,
            render: (_, row) => (
              <Button danger type="text" icon={<DeleteOutlined />}
                aria-label="删除课程时段"
                onClick={() => onChange(value.filter((_, index) => index !== row.key))} />
            ),
          },
        ]}
      />
      <Button
        block
        type="dashed"
        icon={<PlusOutlined />}
        style={{ marginTop: 8 }}
        onClick={() => onChange([...value, {
          weekday: 1,
          period_start: 1,
          period_end: 2,
          week_expr: "1-20周",
          location_code: null,
          course_name: null,
        }])}
      >
        添加课程时段
      </Button>
    </>
  );
}
