import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button, Card, Empty, Input, List, Modal, Select, Space, Tag, Typography } from "antd";
import dayjs from "dayjs";
import { useState } from "react";

import { errorMessage } from "@/api/client";
import { hoursOf, meApi, STATUS_COLOR, STATUS_LABEL, type MyAssignment } from "@/features/me/api";

const EXEC_LABEL: Record<string, string> = {
  pending: "待值班",
  completed: "已完成",
  absent: "未到岗",
  leave: "请假",
  swapped: "已换班",
  task_cancelled: "任务取消",
};

export default function MySchedulePage() {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [leaveFor, setLeaveFor] = useState<MyAssignment | null>(null);
  const [reason, setReason] = useState("");
  const [targetedSwapFor, setTargetedSwapFor] = useState<MyAssignment | null>(null);
  const [targetPersonId, setTargetPersonId] = useState<string | null>(null);
  const [swapReason, setSwapReason] = useState("");

  const schedule = useQuery({ queryKey: ["me", "schedule"], queryFn: meApi.schedule });
  const leaves = useQuery({ queryKey: ["me", "leaves"], queryFn: meApi.leaves });
  const peersQuery = useQuery({ queryKey: ["me", "peers"], queryFn: meApi.peers, enabled: !!targetedSwapFor });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["me"] });
  };

  const createLeave = useMutation({
    mutationFn: () => meApi.createLeave(leaveFor!.assignment_id, reason.trim()),
    onSuccess: (l) => {
      message.success(l.is_emergency ? "已提交（距值班不足 24 小时，标记为紧急请假）" : "请假申请已提交");
      setLeaveFor(null);
      setReason("");
      invalidate();
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const openSwap = useMutation({
    mutationFn: (a: MyAssignment) => meApi.createOpenSwap(a.assignment_id),
    onSuccess: () => {
      message.success("已发布公开替班");
      invalidate();
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const createTargetedSwap = useMutation({
    mutationFn: () =>
      meApi.createTargetedSwap(targetedSwapFor!.assignment_id, targetPersonId!, swapReason.trim() || undefined),
    onSuccess: () => {
      message.success("换班邀请已发送给对方");
      setTargetedSwapFor(null);
      setTargetPersonId(null);
      setSwapReason("");
      invalidate();
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const leaveByAssignment = new Map(
    (leaves.data ?? []).filter((l) => l.status === "pending" || l.status === "approved").map((l) => [l.assignment_id, l]),
  );

  const upcoming = (schedule.data ?? []).filter((a) => dayjs(a.slot_end_at).isAfter(dayjs()));
  const past = (schedule.data ?? []).filter((a) => !dayjs(a.slot_end_at).isAfter(dayjs()));

  const renderItem = (a: MyAssignment, actionable: boolean) => {
    const leave = leaveByAssignment.get(a.assignment_id);
    return (
      <List.Item key={a.assignment_id}>
        <div style={{ width: "100%" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <span style={{ fontWeight: 600 }}>
              {dayjs(a.slot_start_at).format("MM-DD ddd HH:mm")}–{dayjs(a.slot_end_at).format("HH:mm")}
            </span>
            <Tag>{a.venue_name}</Tag>
          </div>
          <div style={{ fontSize: 12, color: "#888", marginTop: 4 }}>
            工时 {hoursOf(a.credited_minutes)}h · {EXEC_LABEL[a.execution_status] ?? a.execution_status}
          </div>
          <div style={{ fontSize: 12, marginTop: 4, color: "#555" }}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px 16px" }}>
              <span>
                <strong>同班同学:</strong>{" "}
                {a.teammates.length > 0
                  ? a.teammates.map((t) => `${t.full_name}(${t.phone})`).join("、")
                  : "无"}
              </span>
              {a.previous_shift && a.previous_shift.length > 0 && (
                <span>
                  <strong>前一班:</strong>{" "}
                  {a.previous_shift.map((t) => `${t.full_name}(${t.phone})`).join("、")}
                </span>
              )}
              {a.next_shift && a.next_shift.length > 0 && (
                <span>
                  <strong>下一班:</strong>{" "}
                  {a.next_shift.map((t) => `${t.full_name}(${t.phone})`).join("、")}
                </span>
              )}
            </div>
          </div>
          {leave && (
            <Tag color={STATUS_COLOR[leave.status]} style={{ marginTop: 6 }}>
              请假{STATUS_LABEL[leave.status]}
            </Tag>
          )}
          {actionable && !leave && (
            <Space style={{ marginTop: 8 }} wrap>
              <Button size="small" onClick={() => setLeaveFor(a)}>
                请假
              </Button>
              <Button size="small" onClick={() => openSwap.mutate(a)} loading={openSwap.isPending}>
                公开替班
              </Button>
              <Button size="small" onClick={() => setTargetedSwapFor(a)}>
                指定换班
              </Button>
            </Space>
          )}
        </div>
      </List.Item>
    );
  };

  return (
    <div>
      <Typography.Title level={4} style={{ marginTop: 0 }}>
        我的排班
      </Typography.Title>

      <Card size="small" title="即将到来" style={{ marginBottom: 12 }} loading={schedule.isLoading}>
        {upcoming.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无待值班次" />
        ) : (
          <List dataSource={upcoming} renderItem={(a) => renderItem(a, true)} />
        )}
      </Card>

      <Card size="small" title="历史记录" loading={schedule.isLoading}>
        {past.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无历史班次" />
        ) : (
          <List dataSource={past} renderItem={(a) => renderItem(a, false)} />
        )}
      </Card>

      <Modal
        open={!!leaveFor}
        title="提交请假申请"
        onCancel={() => setLeaveFor(null)}
        onOk={() => {
          if (!reason.trim()) {
            message.error("请假原因必填");
            return;
          }
          createLeave.mutate();
        }}
        confirmLoading={createLeave.isPending}
        okText="提交"
        cancelText="取消"
      >
        {leaveFor && (
          <p style={{ color: "#888" }}>
            {dayjs(leaveFor.slot_start_at).format("MM-DD HH:mm")}–
            {dayjs(leaveFor.slot_end_at).format("HH:mm")} · {leaveFor.venue_name}
          </p>
        )}
        <Input.TextArea
          rows={3}
          placeholder="请填写请假原因（必填）"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </Modal>

      <Modal
        open={!!targetedSwapFor}
        title="向指定人员发起换班"
        onCancel={() => {
          setTargetedSwapFor(null);
          setTargetPersonId(null);
          setSwapReason("");
        }}
        onOk={() => {
          if (!targetPersonId) {
            message.error("请选择换班对象");
            return;
          }
          createTargetedSwap.mutate();
        }}
        confirmLoading={createTargetedSwap.isPending}
        okText="发送邀请"
        cancelText="取消"
      >
        {targetedSwapFor && (
          <p style={{ color: "#888" }}>
            值班时间：{dayjs(targetedSwapFor.slot_start_at).format("MM-DD HH:mm")}–
            {dayjs(targetedSwapFor.slot_end_at).format("HH:mm")} · {targetedSwapFor.venue_name}
          </p>
        )}
        <div style={{ marginBottom: 12 }}>
          <label style={{ display: "block", marginBottom: 6, fontWeight: 600 }}>选择换班对象:</label>
          <Select
            showSearch
            placeholder="输入姓名或选择人员"
            optionFilterProp="label"
            style={{ width: "100%" }}
            value={targetPersonId}
            onChange={(val) => setTargetPersonId(val)}
            options={(peersQuery.data ?? []).map((p) => ({
              label: `${p.full_name} (${p.class_name})`,
              value: p.id,
            }))}
            loading={peersQuery.isLoading}
          />
        </div>
        <div>
          <label style={{ display: "block", marginBottom: 6, fontWeight: 600 }}>换班原因 (可选):</label>
          <Input.TextArea
            rows={2}
            placeholder="可以写一下换班的缘由"
            value={swapReason}
            onChange={(e) => setSwapReason(e.target.value)}
          />
        </div>
      </Modal>
    </div>
  );
}
