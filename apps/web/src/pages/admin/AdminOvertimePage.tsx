import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button, Card, Space, Table, Tag } from "antd";
import dayjs from "dayjs";

import { errorMessage } from "@/api/client";
import { adminApi } from "@/features/admin/api";
import { STATUS_COLOR, STATUS_LABEL } from "@/features/me/api";

export default function AdminOvertimePage() {
  const { message } = App.useApp();
  const qc = useQueryClient();

  const reqQuery = useQuery({
    queryKey: ["admin", "overtime"],
    queryFn: adminApi.overtime.list,
  });

  const approve = useMutation({
    mutationFn: adminApi.overtime.approve,
    onSuccess: () => {
      message.success("已通过申请");
      qc.invalidateQueries({ queryKey: ["admin", "overtime"] });
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const reject = useMutation({
    mutationFn: adminApi.overtime.reject,
    onSuccess: () => {
      message.success("已拒绝申请");
      qc.invalidateQueries({ queryKey: ["admin", "overtime"] });
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const columns = [
    { title: "申请人", dataIndex: "person_name" },
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
    { title: "原因", dataIndex: "reason" },
    {
      title: "状态",
      dataIndex: "status",
      render: (v: string) => <Tag color={STATUS_COLOR[v]}>{STATUS_LABEL[v] || v}</Tag>,
    },
    {
      title: "提交时间",
      dataIndex: "created_at",
      render: (v: string) => dayjs(v).format("MM-DD HH:mm"),
    },
    {
      title: "操作",
      key: "action",
      render: (_: any, record: any) =>
        record.status === "pending" ? (
          <Space>
            <Button
              type="primary"
              size="small"
              onClick={() => approve.mutate(record.id)}
              loading={approve.isPending}
            >
              通过
            </Button>
            <Button
              danger
              size="small"
              onClick={() => reject.mutate(record.id)}
              loading={reject.isPending}
            >
              拒绝
            </Button>
          </Space>
        ) : null,
    },
  ];

  return (
    <Card title="加班审批">
      <Table
        rowKey="id"
        columns={columns}
        dataSource={reqQuery.data ?? []}
        loading={reqQuery.isLoading}
      />
    </Card>
  );
}
