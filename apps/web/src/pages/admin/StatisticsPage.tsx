import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  App,
  Button,
  Card,
  DatePicker,
  Descriptions,
  Drawer,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Space,
  Spin,
  Statistic,
  Checkbox,
  Table,
  Tag,
  Tabs,
} from "antd";
import dayjs from "dayjs";
import { useState } from "react";

import { errorMessage } from "@/api/client";
import SettingsPage from "@/pages/admin/SettingsPage";
import {
  adminApi,
  type AdjustmentIn,
  type MonthlySummary,
  MONTHLY_STATUS_LABEL,
} from "@/features/admin/api";
import { hoursOf } from "@/features/me/api";

export default function StatisticsPage() {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [month, setMonth] = useState(dayjs().format("YYYY-MM"));

  const query = useQuery({
    queryKey: ["admin", "statistics", "monthly", month],
    queryFn: () => adminApi.statistics.monthly(month),
  });

  const invalidate = () =>
    qc.invalidateQueries({ queryKey: ["admin", "statistics", "monthly", month] });

  const recalcM = useMutation({
    mutationFn: () => adminApi.statistics.recalculate(month),
    onSuccess: (d) => {
      message.success(d.message);
      invalidate();
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const lockM = useMutation({
    mutationFn: () => adminApi.statistics.lock(month),
    onSuccess: (d) => {
      message.success(d.message);
      invalidate();
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const [adjustFor, setAdjustFor] = useState<MonthlySummary | null>(null);
  const [detailFor, setDetailFor] = useState<MonthlySummary | null>(null);

  const data = query.data ?? [];
  const totals = data.reduce(
    (acc, r) => {
      acc.completed += r.completed_minutes;
      acc.balance += r.balance_minutes;
      acc.extra += r.multiplier_extra_minutes;
      return acc;
    },
    { completed: 0, balance: 0, extra: 0 },
  );

  return (
    <Tabs
      defaultActiveKey="stats"
      items={[
        {
          key: "stats",
          label: "月度工时统计与导出",
          children: (
            <Card
              title="月度统计"
              extra={
                <Space wrap>
                  <DatePicker
                    picker="month"
                    value={dayjs(month)}
                    onChange={(v) => v && setMonth(v.format("YYYY-MM"))}
                    allowClear={false}
                  />
                  <Button onClick={() => recalcM.mutate()} loading={recalcM.isPending}>
                    重算
                  </Button>
                  <Popconfirm title="锁定后该月数据不可再重算覆盖" onConfirm={() => lockM.mutate()}>
                    <Button loading={lockM.isPending}>锁定</Button>
                  </Popconfirm>
                  <Button onClick={() => (window.location.href = adminApi.statistics.exportUrl(month))}>
                    导出 Excel
                  </Button>
                </Space>
              }
            >
              {query.isLoading && <Spin />}
              {query.error && (
                <Alert type="info" showIcon message="该月尚无统计，点击「重算」生成" />
              )}
              {data.length > 0 && (
                <Space size="large" style={{ marginBottom: 16 }}>
                  <Statistic title="全员完成工时" value={hoursOf(totals.completed)} suffix="h" />
                  <Statistic title="全员倍率增加" value={hoursOf(totals.extra)} suffix="h" />
                  <Statistic title="人员数" value={data.length} />
                </Space>
              )}

              <Table<MonthlySummary>
                rowKey="person_id"
                loading={query.isLoading}
                dataSource={data}
                pagination={{ pageSize: 20 }}
                locale={{ emptyText: <Empty description="该月暂无统计数据" /> }}
                columns={[
                  { title: "学号", dataIndex: "student_no", width: 110 },
                  { title: "姓名", dataIndex: "person_name", width: 90 },
                  { title: "班级", dataIndex: "class_name", width: 100 },
                  {
                    title: "完成(h)",
                    dataIndex: "completed_minutes",
                    width: 90,
                    render: (v: number) => hoursOf(v),
                  },
                  {
                    title: "倍率(h)",
                    dataIndex: "multiplier_extra_minutes",
                    width: 90,
                    render: (v: number) => hoursOf(v),
                  },
                  { title: "请假", dataIndex: "leave_count", width: 70 },
                  { title: "换出", dataIndex: "swap_out_count", width: 70 },
                  { title: "未到岗", dataIndex: "absence_count", width: 80 },
                  {
                    title: "状态",
                    dataIndex: "status",
                    width: 90,
                    render: (s: string) => (
                      <Tag color={s === "locked" ? "red" : s === "confirmed" ? "green" : "default"}>
                        {MONTHLY_STATUS_LABEL[s] ?? s}
                      </Tag>
                    ),
                  },
                  {
                    title: "操作",
                    width: 140,
                    render: (_, r) => (
                      <Space>
                        <Button size="small" onClick={() => setDetailFor(r)}>
                          明细
                        </Button>
                        {r.status !== "locked" && (
                          <Button size="small" onClick={() => setAdjustFor(r)}>
                            调整
                          </Button>
                        )}
                      </Space>
                    ),
                  },
                ]}
              />

              {adjustFor && (
                <AdjustModal
                  month={month}
                  summary={adjustFor}
                  onClose={() => setAdjustFor(null)}
                  onDone={() => {
                    setAdjustFor(null);
                    invalidate();
                  }}
                />
              )}
              {detailFor && (
                <DetailDrawer month={month} summary={detailFor} onClose={() => setDetailFor(null)} />
              )}
            </Card>
          ),
        },
        {
          key: "settings",
          label: "系统规则与常规配置",
          children: <SettingsPage />,
        },
      ]}
    />
  );
}

function AdjustModal({
  month,
  summary,
  onClose,
  onDone,
}: {
  month: string;
  summary: MonthlySummary;
  onClose: () => void;
  onDone: () => void;
}) {
  const { message } = App.useApp();
  const [form] = Form.useForm<Omit<AdjustmentIn, "person_id">>();
  const m = useMutation({
    mutationFn: (v: AdjustmentIn) => adminApi.statistics.adjust(month, v),
    onSuccess: (d) => {
      message.success(d.message);
      onDone();
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const submit = async () => {
    const v = await form.validateFields();
    m.mutate({ ...v, person_id: summary.person_id });
  };

  return (
    <Modal
      title={`工时调整 - ${summary.person_name ?? summary.person_id.slice(0, 6)}`}
      open
      onOk={submit}
      onCancel={onClose}
      confirmLoading={m.isPending}
      destroyOnClose
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{ minutes_delta: 0, affect_balance: false }}
      >
        <Form.Item
          name="minutes_delta"
          label="分钟数（正数增加，负数扣减）"
          rules={[{ required: true }]}
        >
          <InputNumber />
        </Form.Item>
        <Form.Item name="affect_balance" valuePropName="checked" hidden>
          <Checkbox>同时影响排班平衡工时</Checkbox>
        </Form.Item>
        <Form.Item name="reason" label="原因" rules={[{ required: true }]}>
          <Input.TextArea rows={2} placeholder="如：补录、误录修正" />
        </Form.Item>
      </Form>
    </Modal>
  );
}

function DetailDrawer({
  month,
  summary,
  onClose,
}: {
  month: string;
  summary: MonthlySummary;
  onClose: () => void;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["admin", "statistics", "person-monthly", month, summary.person_id],
    queryFn: () => adminApi.statistics.personMonthly(month, summary.person_id),
  });

  return (
    <Drawer
      title={`月度明细 - ${summary.person_name ?? summary.person_id.slice(0, 6)}（${month}）`}
      open
      onClose={onClose}
      width={560}
    >
      {isLoading || !data ? (
        <Spin />
      ) : (
        <>
          <Descriptions column={2} size="small" bordered style={{ marginBottom: 16 }}>
            <Descriptions.Item label="完成工时">{hoursOf(data.completed_minutes)}h</Descriptions.Item>
            <Descriptions.Item label="倍率增加">{hoursOf(data.multiplier_extra_minutes)}h</Descriptions.Item>
            <Descriptions.Item label="状态">
              {MONTHLY_STATUS_LABEL[data.status] ?? data.status}
            </Descriptions.Item>
            <Descriptions.Item label="请假次数">{data.leave_count}</Descriptions.Item>
            <Descriptions.Item label="换出次数">{data.swap_out_count}</Descriptions.Item>
            <Descriptions.Item label="替班次数">{data.replacement_count}</Descriptions.Item>
            <Descriptions.Item label="未到岗">{data.absence_count}</Descriptions.Item>
          </Descriptions>
          <Card size="small" title="各场地工时">
            <Table
              rowKey="venue_id"
              size="small"
              pagination={false}
              dataSource={data.venues}
              locale={{ emptyText: <Empty description="暂无场地工时" /> }}
              columns={[
                { title: "场地", dataIndex: "venue_name" },
                {
                  title: "完成(h)",
                  dataIndex: "completed_minutes",
                  render: (v: number) => hoursOf(v),
                },
              ]}
            />
          </Card>
        </>
      )}
    </Drawer>
  );
}
