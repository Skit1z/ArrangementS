import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button, Card, DatePicker, Form, Input, Modal, Select, Space, Table, Tag } from "antd";
import dayjs from "dayjs";
import { useState } from "react";

import { errorMessage } from "@/api/client";
import { adminApi, Venue } from "@/features/admin/api";
import { meApi, STATUS_COLOR, STATUS_LABEL } from "@/features/me/api";

export default function OvertimePage() {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);

  const reqQuery = useQuery({
    queryKey: ["me", "overtime"],
    queryFn: meApi.overtime,
  });

  const venuesQuery = useQuery<Venue[]>({
    queryKey: ["venues"],
    queryFn: adminApi.venues.list,
  });

  const columns = [
    { title: "场地", dataIndex: "venue_name" },
    {
      title: "开始时间",
      dataIndex: "start_at",
      render: (v: string) => dayjs(v).format("MM-DD HH:mm"),
    },
    {
      title: "结束时间",
      dataIndex: "end_at",
      render: (v: string) => dayjs(v).format("MM-DD HH:mm"),
    },
    { title: "加班原因", dataIndex: "reason" },
    {
      title: "状态",
      dataIndex: "status",
      render: (v: string) => <Tag color={STATUS_COLOR[v]}>{STATUS_LABEL[v] || v}</Tag>,
    },
    {
      title: "提交时间",
      dataIndex: "created_at",
      render: (v: string) => dayjs(v).format("YYYY-MM-DD HH:mm"),
    },
  ];

  return (
    <Card
      title="加班记录"
      extra={
        <Button type="primary" onClick={() => setCreating(true)}>
          提交加班记录
        </Button>
      }
    >
      <Table
        rowKey="id"
        columns={columns}
        dataSource={reqQuery.data ?? []}
        loading={reqQuery.isLoading}
      />

      {creating && (
        <CreateOvertimeModal
          venues={venuesQuery.data ?? []}
          onClose={() => setCreating(false)}
          onSuccess={() => {
            setCreating(false);
            qc.invalidateQueries({ queryKey: ["me", "overtime"] });
          }}
        />
      )}
    </Card>
  );
}

function CreateOvertimeModal({
  venues,
  onClose,
  onSuccess,
}: {
  venues: Venue[];
  onClose: () => void;
  onSuccess: () => void;
}) {
  const { message } = App.useApp();
  const [form] = Form.useForm();

  const create = useMutation({
    mutationFn: (values: any) => {
      const range = values.time_range;
      return meApi.createOvertime(
        values.venue_id,
        range[0].toISOString(),
        range[1].toISOString(),
        values.reason
      );
    },
    onSuccess: () => {
      message.success("加班申请已提交");
      onSuccess();
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  return (
    <Modal
      title="提交加班记录"
      open
      onCancel={onClose}
      onOk={form.submit}
      confirmLoading={create.isPending}
      destroyOnClose
    >
      <Form form={form} layout="vertical" onFinish={(v) => create.mutate(v)}>
        <Form.Item name="venue_id" label="场地" rules={[{ required: true }]}>
          <Select options={venues.map((v) => ({ label: v.name, value: v.id }))} />
        </Form.Item>
        <Form.Item name="time_range" label="时间 (半小时为颗粒度)" rules={[{ required: true }]}>
          <DatePicker.RangePicker
            showTime={{ format: "HH:mm", minuteStep: 30 }}
            format="YYYY-MM-DD HH:mm"
          />
        </Form.Item>
        <Form.Item name="reason" label="加班原因" rules={[{ required: true }]}>
          <Input.TextArea rows={3} placeholder="请简述加班原因" />
        </Form.Item>
      </Form>
    </Modal>
  );
}
