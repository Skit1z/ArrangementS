import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  App,
  Button,
  Card,
  DatePicker,
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
} from "antd";
import dayjs from "dayjs";
import { useState } from "react";

import { errorMessage } from "@/api/client";
import {
  adminApi,
  TASK_STATUS_COLOR,
  TASK_STATUS_LABEL,
  type Venue,
} from "@/features/admin/api";
import { hoursOf } from "@/features/me/api";

export default function TasksPage() {
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
    <Card title="任务管理">
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
    </Card>
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
