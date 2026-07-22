import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  App,
  Button,
  Card,
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
  Tag,
  TimePicker,
  Typography,
  Tabs,
} from "antd";
import dayjs from "dayjs";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { errorMessage } from "@/api/client";
import TasksPage from "@/pages/admin/TasksPage";
import {
  adminApi,
  VENUE_TYPE_LABEL,
  type Venue,
  type VenueCreate,
  type VenueType,
} from "@/features/admin/api";

export default function VenuesPage() {
  return (
    <Card title="场地管理">
      <VenuesTab />
    </Card>
  );
}

// ============ 场地 Tab ============
function VenuesTab() {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = searchParams.get("tab") || "venues";
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
          venue_type: values.venue_type,
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
    <Tabs
      type="card"
      activeKey={activeTab}
      onChange={(k) => setSearchParams({ tab: k })}
      style={{ marginBottom: 16 }}
      items={[
        {
          key: "venues",
          label: "场地维护",
          children: (
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
          ),
        },
        {
          key: "tasks",
          label: "临时/大型任务管理",
          children: <TasksPage />,
        },
      ]}
    />
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


