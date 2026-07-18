import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  App,
  Button,
  Card,
  DatePicker,
  Drawer,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  TimePicker,
  Typography,
} from "antd";
import dayjs from "dayjs";
import { useState } from "react";

import { errorMessage } from "@/api/client";
import {
  adminApi,
  TASK_STATUS_COLOR,
  TASK_STATUS_LABEL,
  VENUE_TYPE_LABEL,
  type Venue,
  type VenueCreate,
  type VenueType,
} from "@/features/admin/api";
import { hoursOf } from "@/features/me/api";

export default function VenuesPage() {
  return (
    <Card title="场地与任务">
      <Tabs
        defaultActiveKey="venues"
        items={[
          { key: "venues", label: "场地", children: <VenuesTab /> },
          { key: "tasks", label: "任务", children: <TasksTab /> },
        ]}
      />
    </Card>
  );
}

// ============ 场地 Tab ============
function VenuesTab() {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<Venue[]>({
    queryKey: ["admin", "venues"],
    queryFn: adminApi.venues.list,
  });

  const [editing, setEditing] = useState<Venue | null>(null);
  const [creating, setCreating] = useState(false);
  const [form] = Form.useForm<VenueCreate>();
  const [templatesVenue, setTemplatesVenue] = useState<Venue | null>(null);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin", "venues"] });

  const createM = useMutation({
    mutationFn: (v: VenueCreate) => adminApi.venues.create(v),
    onSuccess: () => {
      message.success("场地已创建");
      setCreating(false);
      form.resetFields();
      invalidate();
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const updateM = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<VenueCreate> }) =>
      adminApi.venues.update(id, patch),
    onSuccess: () => {
      message.success("场地已更新");
      setEditing(null);
      invalidate();
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const disableM = useMutation({
    mutationFn: (id: string) => adminApi.venues.disable(id),
    onSuccess: () => {
      message.success("场地已停用");
      invalidate();
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const openCreate = () => {
    form.resetFields();
    form.setFieldsValue({
      venue_type: "event_based",
      default_required_people: 2,
      default_prep_minutes: 30,
      default_cleanup_minutes: 30,
      sort_order: 0,
    });
    setCreating(true);
  };

  const openEdit = (v: Venue) => {
    form.setFieldsValue({
      ...v,
      address: v.address ?? undefined,
    });
    setEditing(v);
  };

  const submit = async () => {
    const values = await form.validateFields();
    if (editing) {
      // venue_type / code 不可改；只提交可改字段
      updateM.mutate({
        id: editing.id,
        patch: {
          name: values.name,
          address: values.address,
          default_required_people: values.default_required_people,
          default_prep_minutes: values.default_prep_minutes,
          default_cleanup_minutes: values.default_cleanup_minutes,
          sort_order: values.sort_order,
        },
      });
    } else {
      createM.mutate(values);
    }
  };

  return (
    <>
      <div style={{ marginBottom: 12 }}>
        <Button type="primary" onClick={openCreate}>
          新建场地
        </Button>
      </div>
      <Table<Venue>
        rowKey="id"
        loading={isLoading}
        dataSource={data}
        pagination={false}
        columns={[
          { title: "名称", dataIndex: "name" },
          { title: "代码", dataIndex: "code", width: 80 },
          {
            title: "类型",
            dataIndex: "venue_type",
            width: 100,
            render: (v: VenueType) => <Tag>{VENUE_TYPE_LABEL[v]}</Tag>,
          },
          { title: "默认人数", dataIndex: "default_required_people", width: 90 },
          { title: "提前(min)", dataIndex: "default_prep_minutes", width: 90 },
          { title: "收尾(min)", dataIndex: "default_cleanup_minutes", width: 90 },
          {
            title: "状态",
            dataIndex: "is_active",
            width: 80,
            render: (v: boolean) => (v ? <Tag color="green">启用</Tag> : <Tag>停用</Tag>),
          },
          {
            title: "操作",
            width: 240,
            render: (_, v) => (
              <Space>
                <Button size="small" onClick={() => openEdit(v)}>
                  编辑
                </Button>
                {v.venue_type === "fixed_shift" && (
                  <Button size="small" onClick={() => setTemplatesVenue(v)}>
                    班次模板
                  </Button>
                )}
                {v.is_active && (
                  <Popconfirm
                    title="停用后历史数据保留，不再用于新排班"
                    onConfirm={() => disableM.mutate(v.id)}
                  >
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
        title={editing ? "编辑场地" : "新建场地"}
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
          <Form.Item name="code" label="代码" rules={[{ required: true }]}>
            <Input disabled={!!editing} />
          </Form.Item>
          <Form.Item name="venue_type" label="类型" rules={[{ required: true }]}>
            <Select
              disabled={!!editing}
              options={[
                { value: "fixed_shift", label: VENUE_TYPE_LABEL.fixed_shift },
                { value: "event_based", label: VENUE_TYPE_LABEL.event_based },
              ]}
            />
          </Form.Item>
          <Form.Item name="address" label="地址">
            <Input />
          </Form.Item>
          <Space wrap>
            <Form.Item name="default_required_people" label="默认人数">
              <InputNumber min={1} />
            </Form.Item>
            <Form.Item name="default_prep_minutes" label="提前到岗(min)">
              <InputNumber min={0} />
            </Form.Item>
            <Form.Item name="default_cleanup_minutes" label="收尾(min)">
              <InputNumber min={0} />
            </Form.Item>
            <Form.Item name="sort_order" label="排序">
              <InputNumber />
            </Form.Item>
          </Space>
        </Form>
      </Modal>

      {templatesVenue && (
        <ShiftTemplatesDrawer venue={templatesVenue} onClose={() => setTemplatesVenue(null)} />
      )}
    </>
  );
}

// ============ 班次模板 Drawer（仅固定班次场地）============
function ShiftTemplatesDrawer({ venue, onClose }: { venue: Venue; onClose: () => void }) {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["admin", "shift-templates", venue.id],
    queryFn: () => adminApi.shiftTemplates.get(venue.id),
  });

  const replaceM = useMutation({
    mutationFn: (templates: Parameters<typeof adminApi.shiftTemplates.replace>[1]) =>
      adminApi.shiftTemplates.replace(venue.id, templates),
    onSuccess: () => {
      message.success("班次模板已保存");
      qc.invalidateQueries({ queryKey: ["admin", "shift-templates", venue.id] });
      onClose();
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  type Row = {
    key: string;
    name: string;
    start_time: dayjs.Dayjs;
    end_time: dayjs.Dayjs;
    credited_minutes: number;
    weekday_required_people: number;
    weekend_required_people: number;
    is_active: boolean;
  };

  const toRows = (): Row[] =>
    (data ?? []).map((t, i) => ({
      key: t.id ?? `row-${i}`,
      name: t.name,
      start_time: dayjs(t.start_time, "HH:mm:ss"),
      end_time: dayjs(t.end_time, "HH:mm:ss"),
      credited_minutes: t.credited_minutes,
      weekday_required_people: t.weekday_required_people,
      weekend_required_people: t.weekend_required_people,
      is_active: t.is_active,
    }));
  const [localRows, setLocalRows] = useState<Row[] | null>(null);
  const rowsToShow = localRows ?? toRows();

  const save = () => {
    const payload = rowsToShow.map((r) => ({
      name: r.name,
      start_time: r.start_time.format("HH:mm:ss"),
      end_time: r.end_time.format("HH:mm:ss"),
      credited_minutes: r.credited_minutes,
      weekday_required_people: r.weekday_required_people,
      weekend_required_people: r.weekend_required_people,
      is_active: r.is_active,
    }));
    replaceM.mutate(payload);
  };

  return (
    <Drawer
      title={`班次模板 - ${venue.name}`}
      open
      onClose={onClose}
      width={720}
      footer={
        <Space style={{ float: "right" }}>
          <Button onClick={onClose}>取消</Button>
          <Button type="primary" loading={replaceM.isPending} onClick={save}>
            保存（整体替换）
          </Button>
        </Space>
      }
    >
      <Typography.Paragraph type="secondary">
        固定班次场地的班次模板。保存时整体替换，credited_minutes 为固定统计工时（不倍率、不取整）。
      </Typography.Paragraph>
      <Button
        style={{ marginBottom: 12 }}
        onClick={() =>
          setLocalRows([
            ...rowsToShow,
            {
              key: `new-${Date.now()}`,
              name: "",
              start_time: dayjs("08:00:00", "HH:mm:ss"),
              end_time: dayjs("10:00:00", "HH:mm:ss"),
              credited_minutes: 120,
              weekday_required_people: 2,
              weekend_required_people: 1,
              is_active: true,
            },
          ])
        }
      >
        新增班次
      </Button>
      <Table
        rowKey="key"
        loading={isLoading}
        dataSource={rowsToShow}
        pagination={false}
        size="small"
        columns={[
          {
            title: "名称",
            dataIndex: "name",
            render: (_, r, i) => (
              <Input
                value={r.name}
                placeholder="如 第1班"
                onChange={(e) => {
                  const next = [...rowsToShow];
                  next[i] = { ...r, name: e.target.value };
                  setLocalRows(next);
                }}
              />
            ),
          },
          {
            title: "开始",
            dataIndex: "start_time",
            render: (_, r, i) => (
              <TimePicker
                value={r.start_time}
                format="HH:mm"
                onChange={(v) => {
                  if (!v) return;
                  const next = [...rowsToShow];
                  next[i] = { ...r, start_time: v };
                  setLocalRows(next);
                }}
              />
            ),
          },
          {
            title: "结束",
            dataIndex: "end_time",
            render: (_, r, i) => (
              <TimePicker
                value={r.end_time}
                format="HH:mm"
                onChange={(v) => {
                  if (!v) return;
                  const next = [...rowsToShow];
                  next[i] = { ...r, end_time: v };
                  setLocalRows(next);
                }}
              />
            ),
          },
          {
            title: "工时(min)",
            dataIndex: "credited_minutes",
            width: 100,
            render: (_, r, i) => (
              <InputNumber
                min={0}
                value={r.credited_minutes}
                onChange={(v) => {
                  const next = [...rowsToShow];
                  next[i] = { ...r, credited_minutes: v ?? 0 };
                  setLocalRows(next);
                }}
              />
            ),
          },
          {
            title: "工作日人数",
            dataIndex: "weekday_required_people",
            width: 110,
            render: (_, r, i) => (
              <InputNumber
                min={0}
                value={r.weekday_required_people}
                onChange={(v) => {
                  const next = [...rowsToShow];
                  next[i] = { ...r, weekday_required_people: v ?? 0 };
                  setLocalRows(next);
                }}
              />
            ),
          },
          {
            title: "周末人数",
            dataIndex: "weekend_required_people",
            width: 100,
            render: (_, r, i) => (
              <InputNumber
                min={0}
                value={r.weekend_required_people}
                onChange={(v) => {
                  const next = [...rowsToShow];
                  next[i] = { ...r, weekend_required_people: v ?? 0 };
                  setLocalRows(next);
                }}
              />
            ),
          },
          {
            title: "启用",
            dataIndex: "is_active",
            width: 60,
            render: (_, r, i) => (
              <Switch
                checked={r.is_active}
                onChange={(v) => {
                  const next = [...rowsToShow];
                  next[i] = { ...r, is_active: v };
                  setLocalRows(next);
                }}
              />
            ),
          },
          {
            title: "",
            width: 60,
            render: (_, _r, i) => (
              <Button
                size="small"
                danger
                onClick={() => {
                  const next = rowsToShow.filter((_, idx) => idx !== i);
                  setLocalRows(next);
                }}
              >
                删
              </Button>
            ),
          },
        ]}
      />
    </Drawer>
  );
}

// ============ 任务 Tab ============
function TasksTab() {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [venueFilter, setVenueFilter] = useState<string | undefined>();
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [includeCancelled, setIncludeCancelled] = useState(false);

  const venuesQ = useQuery<Venue[]>({
    queryKey: ["admin", "venues"],
    queryFn: adminApi.venues.list,
  });

  const tasksQ = useQuery({
    queryKey: ["admin", "tasks", venueFilter, statusFilter, includeCancelled],
    queryFn: () =>
      adminApi.tasks.list({
        venue_id: venueFilter,
        status: statusFilter as Parameters<typeof adminApi.tasks.list>[0] extends { status?: infer S } ? S : never,
        include_cancelled: includeCancelled,
      }),
  });

  const [creating, setCreating] = useState(false);
  const [form] = Form.useForm();
  const [previewId, setPreviewId] = useState<string | null>(null);

  const createM = useMutation({
    mutationFn: (v: Parameters<typeof adminApi.tasks.create>[0]) => adminApi.tasks.create(v),
    onSuccess: () => {
      message.success("任务已创建");
      setCreating(false);
      form.resetFields();
      qc.invalidateQueries({ queryKey: ["admin", "tasks"] });
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const cancelM = useMutation({
    mutationFn: (id: string) => adminApi.tasks.cancel(id),
    onSuccess: () => {
      message.success("任务已取消");
      qc.invalidateQueries({ queryKey: ["admin", "tasks"] });
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const openCreate = () => {
    form.resetFields();
    const firstEvent = (venuesQ.data ?? []).find((v) => v.venue_type === "event_based");
    form.setFieldsValue({
      venue_id: firstEvent?.id,
      booking_range: undefined,
      prep_minutes: 30,
      cleanup_minutes: 30,
      required_people: 2,
      is_temporary: false,
    });
    setCreating(true);
  };

  const submit = async () => {
    const values = await form.validateFields();
    const range: [dayjs.Dayjs, dayjs.Dayjs] = values.booking_range;
    createM.mutate({
      venue_id: values.venue_id,
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
  };

  return (
    <>
      <Space style={{ marginBottom: 12 }} wrap>
        <Select
          allowClear
          placeholder="按场地过滤"
          style={{ width: 160 }}
          value={venueFilter}
          onChange={setVenueFilter}
          options={(venuesQ.data ?? []).map((v) => ({ value: v.id, label: v.name }))}
        />
        <Select
          allowClear
          placeholder="按状态过滤"
          style={{ width: 140 }}
          value={statusFilter}
          onChange={setStatusFilter}
          options={Object.entries(TASK_STATUS_LABEL).map(([value, label]) => ({ value, label }))}
        />
        <span>
          <input
            type="checkbox"
            checked={includeCancelled}
            onChange={(e) => setIncludeCancelled(e.target.checked)}
            style={{ marginRight: 4 }}
          />
          含已取消
        </span>
        <Button type="primary" onClick={openCreate} disabled={!venuesQ.data?.length}>
          新建任务
        </Button>
      </Space>

      <Table
        rowKey="id"
        loading={tasksQ.isLoading}
        dataSource={tasksQ.data}
        pagination={{ pageSize: 20 }}
        columns={[
          { title: "标题", dataIndex: "title" },
          { title: "场地", dataIndex: "venue_name", width: 100 },
          {
            title: "预约时间",
            width: 240,
            render: (_, r) =>
              `${dayjs(r.booking_start_at).format("MM-DD HH:mm")}–${dayjs(r.booking_end_at).format("HH:mm")}`,
          },
          {
            title: "完整值班",
            width: 240,
            render: (_, r) =>
              `${dayjs(r.duty_start_at).format("MM-DD HH:mm")}–${dayjs(r.duty_end_at).format("HH:mm")}`,
          },
          { title: "人数", dataIndex: "required_people", width: 60 },
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
          { title: "v", dataIndex: "version", width: 50 },
          {
            title: "操作",
            width: 160,
            render: (_, r) => (
              <Space>
                <Button size="small" onClick={() => setPreviewId(r.id)}>
                  工时预览
                </Button>
                {r.status !== "cancelled" && r.status !== "completed" && (
                  <Popconfirm title="确认取消该任务？" onConfirm={() => cancelM.mutate(r.id)}>
                    <Button size="small" danger>
                      取消
                    </Button>
                  </Popconfirm>
                )}
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title="新建任务"
        open={creating}
        onOk={submit}
        onCancel={() => setCreating(false)}
        confirmLoading={createM.isPending}
        destroyOnClose
        width={600}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="venue_id" label="场地" rules={[{ required: true }]}>
            <Select
              options={(venuesQ.data ?? [])
                .filter((v) => v.venue_type === "event_based" && v.is_active)
                .map((v) => ({ value: v.id, label: v.name }))}
              placeholder="仅蓝厅/报告厅类场地"
            />
          </Form.Item>
          <Form.Item name="title" label="标题" rules={[{ required: true }]}>
            <Input placeholder="如：开学典礼保障" />
          </Form.Item>
          <Form.Item
            name="booking_range"
            label="预约起止时间"
            rules={[{ required: true, message: "请选择预约时间" }]}
          >
            <DatePicker.RangePicker showTime format="YYYY-MM-DD HH:mm" />
          </Form.Item>
          <Space wrap>
            <Form.Item name="prep_minutes" label="提前到岗(min)">
              <InputNumber min={0} />
            </Form.Item>
            <Form.Item name="cleanup_minutes" label="收尾(min)">
              <InputNumber min={0} />
            </Form.Item>
            <Form.Item name="required_people" label="需求人数">
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
          <Form.Item name="requirements" label="要求">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="notes" label="备注">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      {previewId && (
        <TaskHoursModal taskId={previewId} onClose={() => setPreviewId(null)} />
      )}
    </>
  );
}

function TaskHoursModal({ taskId, onClose }: { taskId: string; onClose: () => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ["admin", "task-hours-preview", taskId],
    queryFn: () => adminApi.tasks.previewHours(taskId),
  });
  return (
    <Modal title="单人工时预览（按完整值班时间与倍率规则）" open onCancel={onClose} footer={null} width={640}>
      {isLoading || !data ? (
        "加载中..."
      ) : (
        <>
          <Space size="large" style={{ marginBottom: 12 }}>
            <span>原始: {hoursOf(data.raw_minutes)}h</span>
            <span>加权前: {hoursOf(data.weighted_minutes_before_round)}h</span>
            <span>
              <strong>计入: {hoursOf(data.credited_minutes)}h</strong>
            </span>
          </Space>
          <Table
            rowKey={(r) => r.start_at}
            size="small"
            pagination={false}
            dataSource={data.segments}
            columns={[
              {
                title: "时段",
                render: (_, r) =>
                  `${dayjs(r.start_at).format("HH:mm")}–${dayjs(r.end_at).format("HH:mm")}`,
              },
              { title: "分钟", dataIndex: "minutes", width: 80 },
              {
                title: "倍率",
                dataIndex: "multiplier",
                width: 80,
                render: (v: number) => `×${v}`,
              },
              { title: "规则", dataIndex: "rule_name", width: 140 },
            ]}
          />
        </>
      )}
    </Modal>
  );
}
