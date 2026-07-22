import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  App,
  Badge,
  Button,
  Card,
  DatePicker,
  Empty,
  Input,
  List,
  Modal,
  Select,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  Typography,
} from "antd";
import dayjs from "dayjs";
import { useState } from "react";

import { errorMessage } from "@/api/client";
import {
  adminApi,
  type AvailabilityRequestItem,
  type DailyAssignment,
  type LeaveItem,
  type SwapItem,
} from "@/features/admin/api";

const { Text } = Typography;

const EXEC_LABEL: Record<string, string> = {
  pending: "待值班",
  completed: "已完成",
  absent: "未到岗",
  leave: "请假",
};
const EXEC_COLOR: Record<string, string> = {
  pending: "default",
  completed: "green",
  absent: "red",
  leave: "orange",
};

import AdminOvertimePage from "@/pages/admin/AdminOvertimePage";

export default function ReviewCenterPage() {
  return (
    <Tabs
      defaultActiveKey="review"
      items={[
        {
          key: "review",
          label: "假勤与换班审核",
          children: (
            <Card
              title={<span style={{ fontSize: 18, fontWeight: 600 }}>假勤与换班审核</span>}
              bordered={false}
              style={{ boxShadow: "0 4px 12px rgba(0,0,0,0.05)", borderRadius: 12 }}
            >
              <Tabs
                defaultActiveKey="availability"
                items={[
                  { key: "availability", label: "不可值班申请", children: <AvailabilityTab /> },
                  { key: "leave", label: "请假", children: <LeaveTab /> },
                  { key: "swap", label: "换班终审", children: <SwapTab /> },
                  { key: "execution", label: "执行状态", children: <ExecutionTab /> },
                ]}
              />
            </Card>
          ),
        },
        {
          key: "overtime",
          label: "加班申请审批",
          children: <AdminOvertimePage />,
        },
      ]}
    />
  );
}

// ============ 不可值班申请 ============
function AvailabilityTab() {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [rejecting, setRejecting] = useState<AvailabilityRequestItem | null>(null);
  const [comment, setComment] = useState("");

  const query = useQuery({
    queryKey: ["admin", "review", "availability"],
    queryFn: adminApi.review.availabilityRequests,
  });

  const approveM = useMutation({
    mutationFn: (id: string) => adminApi.review.approveAvailability(id),
    onSuccess: () => {
      message.success("已通过");
      qc.invalidateQueries({ queryKey: ["admin", "review", "availability"] });
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const rejectM = useMutation({
    mutationFn: () => adminApi.review.rejectAvailability(rejecting!.id, comment.trim() || undefined),
    onSuccess: () => {
      message.success("已驳回");
      setRejecting(null);
      setComment("");
      qc.invalidateQueries({ queryKey: ["admin", "review", "availability"] });
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  if (query.isLoading) return <Spin />;
  const rows = (query.data ?? []).filter((r) => r.status === "pending");

  return (
    <>
      <List
        locale={{ emptyText: <Empty description="暂无待审核申请" /> }}
        dataSource={rows}
        renderItem={(r) => (
          <List.Item
            actions={[
              <Button
                type="primary"
                loading={approveM.isPending}
                onClick={() => approveM.mutate(r.id)}
              >
                通过
              </Button>,
              <Button danger onClick={() => { setRejecting(r); setComment(""); }}>
                驳回
              </Button>,
            ]}
          >
            <List.Item.Meta
              title={`${r.reason || "（无原因）"} · ${dayjs(r.start_at).format("MM-DD HH:mm")}–${dayjs(r.end_at).format("HH:mm")}`}
              description={<Text type="secondary">人员 ID：{r.person_id}</Text>}
            />
          </List.Item>
        )}
      />
      <Modal
        open={!!rejecting}
        title="驳回不可值班申请"
        onCancel={() => setRejecting(null)}
        onOk={() => rejectM.mutate()}
        confirmLoading={rejectM.isPending}
        okText="确认驳回"
        cancelText="取消"
        okButtonProps={{ danger: true }}
      >
        {rejecting && (
          <p style={{ color: "#888" }}>
            {dayjs(rejecting.start_at).format("MM-DD HH:mm")}–
            {dayjs(rejecting.end_at).format("HH:mm")}：{rejecting.reason || "（无原因）"}
          </p>
        )}
        <Input.TextArea
          rows={2}
          placeholder="驳回原因（可选）"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
        />
      </Modal>
    </>
  );
}

// ============ 请假 ============
function LeaveTab() {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [rejecting, setRejecting] = useState<LeaveItem | null>(null);
  const [comment, setComment] = useState("");

  const query = useQuery({
    queryKey: ["admin", "review", "leave"],
    queryFn: adminApi.review.leaveRequests,
  });

  const approveM = useMutation({
    mutationFn: (id: string) => adminApi.review.approveLeave(id),
    onSuccess: () => {
      message.success("已通过");
      qc.invalidateQueries({ queryKey: ["admin", "review", "leave"] });
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const rejectM = useMutation({
    mutationFn: () => adminApi.review.rejectLeave(rejecting!.id, comment.trim() || undefined),
    onSuccess: () => {
      message.success("已驳回");
      setRejecting(null);
      setComment("");
      qc.invalidateQueries({ queryKey: ["admin", "review", "leave"] });
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const revokeM = useMutation({
    mutationFn: (id: string) => adminApi.review.revokeLeaveApproval(id),
    onSuccess: () => {
      message.success("已撤销请假批准并恢复原排班");
      qc.invalidateQueries({ queryKey: ["admin", "review", "leave"] });
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  if (query.isLoading) return <Spin />;
  const rows = query.data ?? [];

  return (
    <>
      <List
        locale={{ emptyText: <Empty description="暂无待审核请假" /> }}
        dataSource={rows}
        renderItem={(r) => (
          <List.Item
            actions={r.status === "approved"
              ? [
                  <Button danger loading={revokeM.isPending} onClick={() => revokeM.mutate(r.id)}>
                    撤销批准
                  </Button>,
                ]
              : [
                  <Button type="primary" loading={approveM.isPending} onClick={() => approveM.mutate(r.id)}>
                    通过
                  </Button>,
                  <Button danger onClick={() => { setRejecting(r); setComment(""); }}>
                    驳回
                  </Button>,
                ]}
          >
            <List.Item.Meta
              title={
                <Space>
                  <span>{r.reason}</span>
                  {r.is_emergency && <Tag color="red">紧急</Tag>}
                  {r.status === "approved" && <Tag color="green">已批准</Tag>}
                </Space>
              }
              description={<Text type="secondary">人员 ID：{r.applicant_person_id}</Text>}
            />
          </List.Item>
        )}
      />
      <Modal
        open={!!rejecting}
        title="驳回请假"
        onCancel={() => setRejecting(null)}
        onOk={() => rejectM.mutate()}
        confirmLoading={rejectM.isPending}
        okText="确认驳回"
        cancelText="取消"
        okButtonProps={{ danger: true }}
      >
        {rejecting && <p style={{ color: "#888" }}>{rejecting.reason}</p>}
        <Input.TextArea
          rows={2}
          placeholder="驳回原因（可选）"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
        />
      </Modal>
    </>
  );
}

// ============ 换班终审 ============
function SwapTab() {
  const { message, modal } = App.useApp();
  const qc = useQueryClient();
  const [rejecting, setRejecting] = useState<SwapItem | null>(null);
  const [comment, setComment] = useState("");
  const [pickingSwap, setPickingSwap] = useState<SwapItem | null>(null);

  const query = useQuery({
    queryKey: ["admin", "review", "swap"],
    queryFn: adminApi.review.swapRequests,
  });

  const approveM = useMutation({
    mutationFn: ({ id, personId }: { id: string; personId?: string }) =>
      adminApi.review.approveSwap(id, personId),
    onSuccess: () => {
      message.success("已通过");
      qc.invalidateQueries({ queryKey: ["admin", "review", "swap"] });
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const rejectM = useMutation({
    mutationFn: () => adminApi.review.rejectSwap(rejecting!.id, comment.trim() || undefined),
    onSuccess: () => {
      message.success("已驳回");
      setRejecting(null);
      setComment("");
      qc.invalidateQueries({ queryKey: ["admin", "review", "swap"] });
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  if (query.isLoading) return <Spin />;
  const rows = (query.data ?? []).filter(
    (r) => r.status === "pending_admin" || r.status === "open_collecting"
  );

  const handleApprove = (s: SwapItem) => {
    // 指定换班：直接用 target_person_id
    // 公开替班：若有多人报名需让 admin 选最终人；只有一个报名则直接选
    if (s.mode === "targeted" && s.target_person_id) {
      modal.confirm({
        title: "确认通过指定换班？",
        content: `将班次转给目标人员（ID: ${s.target_person_id}）`,
        onOk: () => approveM.mutate({ id: s.id, personId: s.target_person_id! }),
      });
    } else {
      setPickingSwap(s);
    }
  };

  return (
    <>
      <Table
        size="small"
        locale={{ emptyText: <Empty description="暂无待审核换班" /> }}
        dataSource={rows}
        rowKey="id"
        pagination={false}
        columns={[
          {
            title: "班次",
            render: (_, r) =>
              r.slot_start_at
                ? `${r.venue_name ?? ""} ${dayjs(r.slot_start_at).format("MM-DD HH:mm")}–${dayjs(r.slot_end_at ? dayjs(r.slot_end_at).format("HH:mm") : "")}`
                : "—",
          },
          { title: "发起人", dataIndex: "requester_name", render: (v) => v ?? "—" },
          {
            title: "模式",
            dataIndex: "mode",
            render: (v) => (v === "targeted" ? "指定换班" : "公开替班"),
          },
          {
            title: "状态",
            dataIndex: "status",
            render: (v) => <Badge status={v === "open_collecting" ? "processing" : "warning"} text={v} />,
          },
          {
            title: "操作",
            render: (_, r) => (
              <Space>
                <Button type="primary" size="small" onClick={() => handleApprove(r)}>
                  通过
                </Button>
                <Button
                  danger
                  size="small"
                  onClick={() => {
                    setRejecting(r);
                    setComment("");
                  }}
                >
                  驳回
                </Button>
              </Space>
            ),
          },
        ]}
      />

      <Modal
        open={!!pickingSwap}
        title="选择最终接替人员"
        onCancel={() => setPickingSwap(null)}
        footer={null}
      >
        {pickingSwap && (
          <PickPersonForSwap
            swap={pickingSwap}
            onSubmit={(personId) => {
              approveM.mutate({ id: pickingSwap.id, personId });
              setPickingSwap(null);
            }}
          />
        )}
      </Modal>

      <Modal
        open={!!rejecting}
        title="驳回换班"
        onCancel={() => setRejecting(null)}
        onOk={() => rejectM.mutate()}
        confirmLoading={rejectM.isPending}
        okText="确认驳回"
        cancelText="取消"
        okButtonProps={{ danger: true }}
      >
        <Input.TextArea
          rows={2}
          placeholder="驳回原因（可选）"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
        />
      </Modal>
    </>
  );
}

function PickPersonForSwap({ swap, onSubmit }: { swap: SwapItem; onSubmit: (personId: string) => void }) {
  const [pid, setPid] = useState<string>("");
  const candidates = swap.candidates.filter((candidate) => candidate.status === "applied");
  return (
    <div>
      <Select
        style={{ width: "100%" }}
        placeholder={candidates.length ? "请选择已报名人员" : "暂无有效报名人员"}
        value={pid}
        onChange={setPid}
        options={candidates.map((candidate) => ({
          value: candidate.candidate_person_id,
          label: candidate.candidate_name ?? candidate.candidate_person_id,
        }))}
      />
      <div style={{ marginTop: 12, textAlign: "right" }}>
        <Button
          type="primary"
          disabled={!pid.trim()}
          onClick={() => onSubmit(pid.trim())}
        >
          确认通过
        </Button>
      </div>
    </div>
  );
}

// ============ 执行状态（标记未到岗 / 完成） ============
function ExecutionTab() {
  const { message, modal } = App.useApp();
  const qc = useQueryClient();
  const [day, setDay] = useState<dayjs.Dayjs>(dayjs());

  const query = useQuery({
    queryKey: ["admin", "review", "execution", day.format("YYYY-MM-DD")],
    queryFn: () => adminApi.review.dailyAssignments(day.format("YYYY-MM-DD")),
  });

  const markAbsentM = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      adminApi.review.markAbsent(id, reason),
    onSuccess: () => {
      message.success("已标记未到岗");
      qc.invalidateQueries({ queryKey: ["admin", "review", "execution"] });
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const markCompletedM = useMutation({
    mutationFn: (id: string) => adminApi.review.markCompleted(id),
    onSuccess: () => {
      message.success("已标记完成");
      qc.invalidateQueries({ queryKey: ["admin", "review", "execution"] });
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const handleAbsent = (row: DailyAssignment) => {
    let reason = "";
    modal.confirm({
      title: "标记未到岗？",
      content: (
        <Input.TextArea
          rows={2}
          placeholder="未到岗原因（必填）"
          onChange={(e) => { reason = e.target.value; }}
        />
      ) as any,
      onOk: () => {
        if (!reason.trim()) {
          message.error("请填写未到岗原因");
          return Promise.reject();
        }
        markAbsentM.mutate({ id: row.assignment_id, reason: reason.trim() });
      },
    });
  };

  const rows = query.data ?? [];

  return (
    <>
      <div style={{ marginBottom: 12 }}>
        <Space>
          <span>日期：</span>
          <DatePicker
            value={day}
            onChange={(d) => d && setDay(d)}
            allowClear={false}
          />
        </Space>
      </div>
      <Table
        size="small"
        loading={query.isLoading}
        locale={{ emptyText: <Empty description="当天无排班" /> }}
        dataSource={rows}
        rowKey="assignment_id"
        pagination={false}
        columns={[
          {
            title: "时段",
            render: (_, r) =>
              `${dayjs(r.slot_start_at).format("HH:mm")}-${dayjs(r.slot_end_at).format("HH:mm")}`,
            width: 120,
          },
          { title: "场地", dataIndex: "venue_name", width: 120 },
          { title: "人员", dataIndex: "person_name", width: 100 },
          {
            title: "状态",
            dataIndex: "execution_status",
            width: 100,
            render: (v: string) => (
              <Tag color={EXEC_COLOR[v] ?? "default"}>{EXEC_LABEL[v] ?? v}</Tag>
            ),
          },
          {
            title: "操作",
            width: 200,
            render: (_, r) => (
              <Space>
                <Button
                  size="small"
                  type="primary"
                  ghost
                  disabled={r.execution_status === "completed"}
                  loading={markCompletedM.isPending}
                  onClick={() => markCompletedM.mutate(r.assignment_id)}
                >
                  标记完成
                </Button>
                <Button
                  size="small"
                  danger
                  disabled={r.execution_status === "absent" || r.execution_status === "completed"}
                  loading={markAbsentM.isPending}
                  onClick={() => handleAbsent(r)}
                >
                  未到岗
                </Button>
              </Space>
            ),
          },
        ]}
      />
    </>
  );
}
