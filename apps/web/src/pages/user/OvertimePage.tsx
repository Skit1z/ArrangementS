import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button, Card, DatePicker, Form, Grid, Input, List, Modal, Select, Space, Table, Tag } from "antd";
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

  const screens = Grid.useBreakpoint();
  const isMobile = !screens.md;

  return (
    <Card
      title="加班记录"
      extra={
        isMobile ? null : (
          <Button type="primary" onClick={() => setCreating(true)}>
            提交加班记录
          </Button>
        )
      }
    >
      {isMobile && (
        <Button
          type="primary"
          block
          onClick={() => setCreating(true)}
          style={{ marginBottom: 16 }}
        >
          提交加班记录
        </Button>
      )}
      {isMobile ? (
        <List
          loading={reqQuery.isLoading}
          dataSource={reqQuery.data ?? []}
          renderItem={(item: any) => (
            <List.Item key={item.id}>
              <div style={{ width: "100%", padding: "4px 0" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                  <span style={{ fontWeight: 600, fontSize: 14 }}>{item.venue_name}</span>
                  <Tag color={STATUS_COLOR[item.status]}>{STATUS_LABEL[item.status] || item.status}</Tag>
                </div>
                <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>
                  时间：{dayjs(item.start_at).format("MM-DD HH:mm")} ~ {dayjs(item.end_at).format("MM-DD HH:mm")}
                </div>
                <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>
                  原因：{item.reason}
                </div>
                <div style={{ fontSize: 11, color: "#999", marginTop: 4, textAlign: "right" }}>
                  提交于：{dayjs(item.created_at).format("YYYY-MM-DD HH:mm")}
                </div>
              </div>
            </List.Item>
          )}
        />
      ) : (
        <Table
          rowKey="id"
          columns={columns}
          dataSource={reqQuery.data ?? []}
          loading={reqQuery.isLoading}
        />
      )}

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
      return meApi.createOvertime(
        values.venue_id,
        values.start_at.toISOString(),
        values.end_at.toISOString(),
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
        <Form.Item name="start_at" label="开始时间 (半小时为单位)" rules={[{ required: true }]}>
          <DatePicker
            showTime={{ format: "HH:mm", minuteStep: 30 }}
            format="YYYY-MM-DD HH:mm"
            style={{ width: "100%" }}
            placeholder="选择开始时间"
          />
        </Form.Item>
        <Form.Item name="end_at" label="结束时间 (半小时为单位)" rules={[{ required: true }]}>
          <DatePicker
            showTime={{ format: "HH:mm", minuteStep: 30 }}
            format="YYYY-MM-DD HH:mm"
            style={{ width: "100%" }}
            placeholder="选择结束时间"
          />
        </Form.Item>
        <Form.Item name="reason" label="加班原因" rules={[{ required: true }]}>
          <Input.TextArea rows={3} placeholder="请简述加班原因" />
        </Form.Item>
      </Form>
    </Modal>
  );
}
