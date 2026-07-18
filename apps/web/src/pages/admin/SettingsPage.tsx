import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  App,
  Button,
  Card,
  Checkbox,
  DatePicker,
  Drawer,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  TimePicker,
} from "antd";
import dayjs from "dayjs";
import { useState } from "react";

import { errorMessage } from "@/api/client";
import {
  adminApi,
  type AuditLog,
  DAY_TYPE_LABEL,
  type DayType,
  type HolidaySyncItem,
  type MultiplierRule,
  type MultiplierRuleIn,
  type Semester,
  type SemesterCreate,
  type SemesterUpdate,
  type SpecialDate,
  type SpecialDateIn,
  type Vacation,
  type VacationCreate,
} from "@/features/admin/api";

export default function SettingsPage() {
  return (
    <Card title="系统配置">
      <Tabs
        defaultActiveKey="multipliers"
        items={[
          { key: "multipliers", label: "倍率规则", children: <MultipliersTab /> },
          { key: "special", label: "特殊日期", children: <SpecialDatesTab /> },
          { key: "semester", label: "学期设置", children: <SemesterTab /> },
          { key: "vacations", label: "寒暑假管理", children: <VacationsTab /> },
          { key: "audit", label: "审计日志", children: <AuditTab /> },
        ]}
      />
    </Card>
  );
}

// ============ 倍率规则 Tab ============
function MultipliersTab() {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<MultiplierRule[]>({
    queryKey: ["admin", "multipliers"],
    queryFn: adminApi.multipliers.list,
  });
  const venuesQ = useQuery({
    queryKey: ["admin", "venues"],
    queryFn: adminApi.venues.list,
  });

  const [editing, setEditing] = useState<MultiplierRule | null>(null);
  const [creating, setCreating] = useState(false);
  // 表单态：时间用 Dayjs，提交时格式化；不直接绑定 MultiplierRuleIn（其 start/end 是字符串）
  const [form] = Form.useForm<{
    name: string;
    start_time: dayjs.Dayjs;
    end_time: dayjs.Dayjs;
    multiplier: string;
    venue_id?: string | null;
    weekdays?: number[] | null;
    priority?: number;
    is_active?: boolean;
  }>();
  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin", "multipliers"] });

  const createM = useMutation({
    mutationFn: (v: MultiplierRuleIn) => adminApi.multipliers.create(v),
    onSuccess: () => {
      message.success("倍率规则已创建");
      setCreating(false);
      form.resetFields();
      invalidate();
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const updateM = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: MultiplierRuleIn }) =>
      adminApi.multipliers.update(id, patch),
    onSuccess: () => {
      message.success("倍率规则已更新");
      setEditing(null);
      invalidate();
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const disableM = useMutation({
    mutationFn: (id: string) => adminApi.multipliers.disable(id),
    onSuccess: () => {
      message.success("已停用");
      invalidate();
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const openCreate = () => {
    form.resetFields();
    form.setFieldsValue({
      start_time: dayjs("00:00:00", "HH:mm:ss"),
      end_time: dayjs("08:00:00", "HH:mm:ss"),
      multiplier: "2.0",
      priority: 0,
      is_active: true,
    });
    setCreating(true);
  };

  const openEdit = (r: MultiplierRule) => {
    form.setFieldsValue({
      name: r.name,
      start_time: dayjs(r.start_time, "HH:mm:ss"),
      end_time: dayjs(r.end_time, "HH:mm:ss"),
      multiplier: r.multiplier,
      venue_id: r.venue_id ?? undefined,
      weekdays: r.weekdays ?? undefined,
      priority: r.priority,
      is_active: r.is_active,
    });
    setEditing(r);
  };

  const submit = async () => {
    const v = await form.validateFields();
    const payload: MultiplierRuleIn = {
      name: v.name,
      start_time: (v.start_time as dayjs.Dayjs).format("HH:mm:ss"),
      end_time: (v.end_time as dayjs.Dayjs).format("HH:mm:ss"),
      multiplier: v.multiplier,
      venue_id: v.venue_id ?? null,
      weekdays: v.weekdays ?? null,
      priority: v.priority ?? 0,
      is_active: v.is_active ?? true,
    };
    if (editing) updateM.mutate({ id: editing.id, patch: payload });
    else createM.mutate(payload);
  };

  const venueName = (id: string | null) =>
    id ? (venuesQ.data ?? []).find((v) => v.id === id)?.name ?? id.slice(0, 6) : "全部";

  return (
    <>
      <div style={{ marginBottom: 12 }}>
        <Button type="primary" onClick={openCreate}>
          新增倍率规则
        </Button>
      </div>
      <Table<MultiplierRule>
        rowKey="id"
        loading={isLoading}
        dataSource={data}
        pagination={false}
        columns={[
          { title: "名称", dataIndex: "name" },
          {
            title: "时段",
            width: 140,
            render: (_, r) => `${r.start_time}–${r.end_time}`,
          },
          { title: "倍率", dataIndex: "multiplier", width: 80, render: (v) => `×${v}` },
          { title: "场地", width: 100, render: (_, r) => venueName(r.venue_id) },
          {
            title: "星期",
            dataIndex: "weekdays",
            width: 140,
            render: (w: number[] | null) =>
              w && w.length ? w.map((d) => "日一二三四五六"[d]).join("") : "全部",
          },
          { title: "优先级", dataIndex: "priority", width: 80 },
          {
            title: "状态",
            dataIndex: "is_active",
            width: 80,
            render: (v: boolean) => (v ? <Tag color="green">启用</Tag> : <Tag>停用</Tag>),
          },
          {
            title: "操作",
            width: 160,
            render: (_, r) => (
              <Space>
                <Button size="small" onClick={() => openEdit(r)}>
                  编辑
                </Button>
                {r.is_active && (
                  <Popconfirm title="停用该规则？" onConfirm={() => disableM.mutate(r.id)}>
                    <Button size="small" danger>
                      停用
                    </Button>
                  </Popconfirm>
                )}
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title={editing ? "编辑倍率规则" : "新增倍率规则"}
        open={creating || !!editing}
        onOk={submit}
        onCancel={() => {
          setCreating(false);
          setEditing(null);
        }}
        confirmLoading={createM.isPending || updateM.isPending}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Space>
            <Form.Item name="start_time" label="开始时间" rules={[{ required: true }]}>
              <TimePicker format="HH:mm" />
            </Form.Item>
            <Form.Item name="end_time" label="结束时间" rules={[{ required: true }]}>
              <TimePicker format="HH:mm" />
            </Form.Item>
            <Form.Item name="multiplier" label="倍率" rules={[{ required: true }]}>
              <Input placeholder="如 2.0" style={{ width: 100 }} />
            </Form.Item>
            <Form.Item name="priority" label="优先级">
              <InputNumber />
            </Form.Item>
          </Space>
          <Form.Item name="venue_id" label="适用场地（留空=全部）">
            <Select
              allowClear
              placeholder="全部场地"
              options={(venuesQ.data ?? []).map((v) => ({ value: v.id, label: v.name }))}
            />
          </Form.Item>
          <Form.Item name="weekdays" label="适用星期（留空=全部）">
            <Checkbox.Group
              options={[
                { label: "一", value: 1 },
                { label: "二", value: 2 },
                { label: "三", value: 3 },
                { label: "四", value: 4 },
                { label: "五", value: 5 },
                { label: "六", value: 6 },
                { label: "日", value: 0 },
              ]}
            />
          </Form.Item>
          <Form.Item name="is_active" label="启用" valuePropName="checked">
            <Checkbox>启用</Checkbox>
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}

// ============ 特殊日期 Tab ============
function SpecialDatesTab() {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [year, setYear] = useState<number>(dayjs().year());
  const { data, isLoading } = useQuery<SpecialDate[]>({
    queryKey: ["admin", "special-dates", year],
    queryFn: () => adminApi.specialDates.list(year),
  });

  const [creating, setCreating] = useState(false);
  // 表单 date 为 Dayjs，提交时格式化；不直接绑定 SpecialDateIn（其 date 是字符串）
  const [form] = Form.useForm<{
    date: dayjs.Dayjs;
    day_type: DayType;
    custom_required_people?: number | null;
    reason?: string;
  }>();
  const [syncOpen, setSyncOpen] = useState(false);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin", "special-dates", year] });

  const createM = useMutation({
    mutationFn: (v: SpecialDateIn) => adminApi.specialDates.create(v),
    onSuccess: () => {
      message.success("特殊日期已保存");
      setCreating(false);
      form.resetFields();
      invalidate();
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const openCreate = () => {
    form.resetFields();
    form.setFieldsValue({ date: dayjs(), day_type: "closed" });
    setCreating(true);
  };

  const submit = async () => {
    const v = await form.validateFields();
    const payload: SpecialDateIn = {
      date: v.date.format("YYYY-MM-DD"),
      day_type: v.day_type,
      custom_required_people: v.custom_required_people ?? null,
      reason: v.reason,
    };
    createM.mutate(payload);
  };

  return (
    <>
      <Space style={{ marginBottom: 12 }}>
        <DatePicker
          picker="year"
          value={dayjs().year(year)}
          onChange={(v) => v && setYear(v.year())}
          allowClear={false}
        />
        <Button type="primary" onClick={openCreate}>
          手动新增
        </Button>
        <Button onClick={() => setSyncOpen(true)}>节假日同步</Button>
      </Space>
      <Table<SpecialDate>
        rowKey="id"
        loading={isLoading}
        dataSource={data}
        pagination={false}
        columns={[
          { title: "日期", dataIndex: "date", width: 120 },
          {
            title: "类型",
            dataIndex: "day_type",
            width: 140,
            render: (d: DayType) => DAY_TYPE_LABEL[d],
          },
          {
            title: "自定义人数",
            dataIndex: "custom_required_people",
            width: 110,
            render: (v: number | null) => (v === null ? "—" : v),
          },
          { title: "原因", dataIndex: "reason" },
          {
            title: "来源",
            dataIndex: "source",
            width: 100,
            render: (s: string) => (s === "holiday_sync" ? <Tag>同步</Tag> : <Tag>手动</Tag>),
          },
        ]}
      />

      <Modal
        title="新增特殊日期"
        open={creating}
        onOk={submit}
        onCancel={() => setCreating(false)}
        confirmLoading={createM.isPending}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="date" label="日期" rules={[{ required: true }]}>
            <DatePicker format="YYYY-MM-DD" />
          </Form.Item>
          <Form.Item name="day_type" label="类型" rules={[{ required: true }]}>
            <Select
              options={Object.entries(DAY_TYPE_LABEL).map(([value, label]) => ({ value, label }))}
            />
          </Form.Item>
          <Form.Item name="custom_required_people" label="自定义人数（custom 类型时生效）">
            <InputNumber min={0} />
          </Form.Item>
          <Form.Item name="reason" label="原因">
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      {syncOpen && (
        <HolidaySyncDrawer
          year={year}
          onClose={() => setSyncOpen(false)}
          onDone={() => {
            setSyncOpen(false);
            invalidate();
          }}
        />
      )}
    </>
  );
}

function HolidaySyncDrawer({
  year,
  onClose,
  onDone,
}: {
  year: number;
  onClose: () => void;
  onDone: () => void;
}) {
  const { message } = App.useApp();
  const [items, setItems] = useState<HolidaySyncItem[] | null>(null);

  const previewM = useMutation({
    mutationFn: () => adminApi.specialDates.sync(year),
    onSuccess: (d) => {
      setItems(d);
      message.info(`获取 ${d.length} 条，请勾选后确认`);
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const confirmM = useMutation({
    mutationFn: (selected: HolidaySyncItem[]) => adminApi.specialDates.confirmSync(selected),
    onSuccess: (d) => {
      message.success(d.message);
      onDone();
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const [selectedKeys, setSelectedKeys] = useState<React.Key[]>([]);

  return (
    <Drawer
      title={`节假日同步 - ${year}`}
      open
      onClose={onClose}
      width={640}
      footer={
        <Space style={{ float: "right" }}>
          <Button onClick={onClose}>取消</Button>
          <Button
            type="primary"
            loading={confirmM.isPending}
            disabled={!items || selectedKeys.length === 0}
            onClick={() => {
              const selected = (items ?? []).filter((it) =>
                selectedKeys.includes(it.date),
              );
              confirmM.mutate(selected);
            }}
          >
            确认写入 {selectedKeys.length > 0 ? `(${selectedKeys.length})` : ""}
          </Button>
        </Space>
      }
    >
      <Space direction="vertical" style={{ width: "100%" }}>
        <Button type="primary" loading={previewM.isPending} onClick={() => previewM.mutate()}>
          从 holiday-cn 拉取预览
        </Button>
        {items && (
          <Table
            rowKey="date"
            size="small"
            pagination={false}
            dataSource={items}
            rowSelection={{
              selectedRowKeys: selectedKeys,
              onChange: setSelectedKeys,
            }}
            columns={[
              { title: "日期", dataIndex: "date", width: 110 },
              { title: "名称", dataIndex: "reason" },
              {
                title: "类型",
                dataIndex: "day_type",
                width: 110,
                render: (d: DayType) => DAY_TYPE_LABEL[d],
              },
              {
                title: "状态",
                dataIndex: "status",
                width: 90,
                render: (s?: string) => {
                  if (s === "new") return <Tag color="blue">新增</Tag>;
                  if (s === "conflict") return <Tag color="orange">冲突</Tag>;
                  if (s === "same") return <Tag>一致</Tag>;
                  return null;
                },
              },
            ]}
          />
        )}
      </Space>
    </Drawer>
  );
}

// ============ 学期设置 Tab ============
function SemesterTab() {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<Semester[]>({
    queryKey: ["admin", "semesters"],
    queryFn: adminApi.semesters.list,
  });

  const [editing, setEditing] = useState<Semester | null>(null);
  const [creating, setCreating] = useState(false);
  // 表单 first_monday 用 Dayjs，提交时格式化；不直接绑定 SemesterCreate（其是字符串）
  const [form] = Form.useForm<{
    name: string;
    first_monday: dayjs.Dayjs;
    week_count: number;
    course_buffer_enabled: boolean;
    course_buffer_minutes: number;
  }>();

  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin", "semesters"] });

  const createM = useMutation({
    mutationFn: (v: SemesterCreate) => adminApi.semesters.create(v),
    onSuccess: () => {
      message.success("学期已创建");
      setCreating(false);
      form.resetFields();
      invalidate();
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const updateM = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: SemesterUpdate }) =>
      adminApi.semesters.update(id, patch),
    onSuccess: () => {
      message.success("学期已更新");
      setEditing(null);
      invalidate();
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const activateM = useMutation({
    mutationFn: (id: string) => adminApi.semesters.activate(id),
    onSuccess: () => {
      message.success("已设为当前学期");
      invalidate();
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const openCreate = () => {
    form.resetFields();
    form.setFieldsValue({ week_count: 20, course_buffer_enabled: false, course_buffer_minutes: 10 });
    setCreating(true);
  };

  const openEdit = (s: Semester) => {
    form.setFieldsValue({
      name: s.name,
      first_monday: dayjs(s.first_monday),
      week_count: s.week_count,
      course_buffer_enabled: s.course_buffer_enabled,
      course_buffer_minutes: s.course_buffer_minutes,
    });
    setEditing(s);
  };

  const submit = async () => {
    const v = await form.validateFields();
    const payload = {
      name: v.name,
      first_monday: (v.first_monday as dayjs.Dayjs).format("YYYY-MM-DD"),
      week_count: v.week_count,
      course_buffer_enabled: v.course_buffer_enabled,
      course_buffer_minutes: v.course_buffer_minutes,
    };
    if (editing) updateM.mutate({ id: editing.id, patch: payload });
    else createM.mutate({ ...payload, is_current: false });
  };

  return (
    <>
      <div style={{ marginBottom: 12 }}>
        <Button type="primary" onClick={openCreate}>
          新增学期
        </Button>
      </div>
      <Table<Semester>
        rowKey="id"
        loading={isLoading}
        dataSource={data}
        pagination={false}
        columns={[
          { title: "名称", dataIndex: "name" },
          { title: "首周周一", dataIndex: "first_monday", width: 120 },
          { title: "周数", dataIndex: "week_count", width: 80 },
          {
            title: "当前",
            dataIndex: "is_current",
            width: 80,
            render: (v: boolean) => (v ? <Tag color="green">当前</Tag> : <Tag>—</Tag>),
          },
          {
            title: "课程缓冲",
            width: 120,
            render: (_, r) =>
              r.course_buffer_enabled ? `启用 +${r.course_buffer_minutes}min` : "关闭",
          },
          {
            title: "操作",
            width: 200,
            render: (_, r) => (
              <Space>
                <Button size="small" onClick={() => openEdit(r)}>
                  编辑
                </Button>
                {!r.is_current && (
                  <Popconfirm title="设为当前学期？" onConfirm={() => activateM.mutate(r.id)}>
                    <Button size="small" type="primary">
                      设为当前
                    </Button>
                  </Popconfirm>
                )}
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title={editing ? "编辑学期" : "新增学期"}
        open={creating || !!editing}
        onOk={submit}
        onCancel={() => {
          setCreating(false);
          setEditing(null);
        }}
        confirmLoading={createM.isPending || updateM.isPending}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="如 2026 秋季" />
          </Form.Item>
          <Form.Item name="first_monday" label="首周周一" rules={[{ required: true }]}>
            <DatePicker picker="date" format="YYYY-MM-DD" />
          </Form.Item>
          <Form.Item
            name="week_count"
            label="周数（1-30，默认 20）"
            rules={[{ required: true, type: "number", min: 1, max: 30 }]}
          >
            <InputNumber min={1} max={30} />
          </Form.Item>
          <Form.Item name="course_buffer_enabled" label="启用课程缓冲" valuePropName="checked">
            <Checkbox>启用（课表时间前后加缓冲分钟）</Checkbox>
          </Form.Item>
          <Form.Item name="course_buffer_minutes" label="缓冲分钟">
            <InputNumber min={0} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}

// ============ 寒暑假管理 Tab ============
function VacationsTab() {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<Vacation[]>({
    queryKey: ["admin", "vacations"],
    queryFn: adminApi.vacations.list,
  });
  const semestersQ = useQuery({
    queryKey: ["admin", "semesters"],
    queryFn: adminApi.semesters.list,
  });

  const [creating, setCreating] = useState(false);
  const [form] = Form.useForm();
  
  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin", "vacations"] });

  const createM = useMutation({
    mutationFn: (v: VacationCreate) => adminApi.vacations.create(v),
    onSuccess: () => {
      message.success("寒暑假已创建");
      setCreating(false);
      form.resetFields();
      invalidate();
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const disableM = useMutation({
    mutationFn: (id: string) => adminApi.vacations.disable(id),
    onSuccess: () => {
      message.success("寒暑假已停用");
      invalidate();
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const openCreate = () => {
    form.resetFields();
    setCreating(true);
  };

  const submit = async () => {
    const v = await form.validateFields();
    createM.mutate({
      name: v.name,
      start_date: v.dateRange[0].format("YYYY-MM-DD"),
      end_date: v.dateRange[1].format("YYYY-MM-DD"),
      semester_id: v.semester_id,
      required_people: v.required_people,
    });
  };

  return (
    <>
      <div style={{ marginBottom: 12 }}>
        <Button type="primary" onClick={openCreate}>
          新增寒暑假
        </Button>
      </div>
      <Table<Vacation>
        rowKey="id"
        loading={isLoading}
        dataSource={data}
        pagination={false}
        columns={[
          { title: "名称", dataIndex: "name" },
          { title: "开始日期", dataIndex: "start_date" },
          { title: "结束日期", dataIndex: "end_date" },
          {
            title: "学期",
            dataIndex: "semester_id",
            render: (id) => semestersQ.data?.find((s) => s.id === id)?.name ?? id,
          },
          {
            title: "状态",
            dataIndex: "is_active",
            width: 80,
            render: (v: boolean) => (v ? <Tag color="green">启用</Tag> : <Tag>停用</Tag>),
          },
          {
            title: "操作",
            width: 120,
            render: (_, r) => (
              <Space>
                {r.is_active && (
                  <Popconfirm title="确认停用？" onConfirm={() => disableM.mutate(r.id)}>
                    <Button size="small" danger>
                      停用
                    </Button>
                  </Popconfirm>
                )}
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title="新增寒暑假"
        open={creating}
        onOk={submit}
        onCancel={() => setCreating(false)}
        confirmLoading={createM.isPending}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="如 2026 寒假" />
          </Form.Item>
          <Form.Item name="dateRange" label="起止日期" rules={[{ required: true }]}>
            <DatePicker.RangePicker format="YYYY-MM-DD" />
          </Form.Item>
          <Form.Item name="semester_id" label="关联学期" rules={[{ required: true }]}>
            <Select
              options={(semestersQ.data ?? []).map((s) => ({ value: s.id, label: s.name }))}
            />
          </Form.Item>
          <Form.Item name="required_people" label="默认需求人数">
            <InputNumber min={0} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}

// ============ 审计日志 Tab（只读）============
function AuditTab() {
  const { data, isLoading } = useQuery<AuditLog[]>({
    queryKey: ["admin", "audit-logs"],
    queryFn: () => adminApi.auditLogs.list(200),
  });

  return (
    <Table<AuditLog>
      rowKey="id"
      loading={isLoading}
      dataSource={data}
      pagination={{ pageSize: 50 }}
      columns={[
        {
          title: "时间",
          dataIndex: "created_at",
          width: 160,
          render: (t: string) => dayjs(t).format("YYYY-MM-DD HH:mm:ss"),
        },
        { title: "操作人", dataIndex: "actor_username", width: 100 },
        { title: "动作", dataIndex: "action", width: 180 },
        { title: "实体", dataIndex: "entity_type", width: 120 },
        { title: "实体 ID", dataIndex: "entity_id", width: 160 },
        { title: "原因", dataIndex: "reason" },
      ]}
    />
  );
}
