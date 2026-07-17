import { useQuery } from "@tanstack/react-query";
import { Badge, Card, Empty, List, Skeleton, Statistic, Tag, Typography } from "antd";
import dayjs from "dayjs";
import { useNavigate } from "react-router-dom";

import { hoursOf, meApi } from "@/features/me/api";
import { useAuth } from "@/stores/auth";

export default function HomePage() {
  const user = useAuth((s) => s.user);
  const navigate = useNavigate();
  const month = dayjs().format("YYYY-MM");

  const nextDuty = useQuery({ queryKey: ["me", "next-duty"], queryFn: meApi.nextDuty });
  const hours = useQuery({ queryKey: ["me", "hours", month], queryFn: () => meApi.hours(month) });
  const invitations = useQuery({ queryKey: ["me", "invitations"], queryFn: meApi.invitations });
  const leaves = useQuery({ queryKey: ["me", "leaves"], queryFn: meApi.leaves });

  const pendingLeaves = (leaves.data ?? []).filter((l) => l.status === "pending");

  return (
    <div>
      <Typography.Title level={4} style={{ marginTop: 0 }}>
        你好，{user?.username}
      </Typography.Title>

      <Card size="small" title="下一次值班" style={{ marginBottom: 12 }}>
        {nextDuty.isLoading ? (
          <Skeleton active paragraph={{ rows: 1 }} />
        ) : nextDuty.data ? (
          <div>
            <div style={{ fontSize: 16, fontWeight: 600 }}>
              {dayjs(nextDuty.data.slot_start_at).format("MM-DD ddd HH:mm")} –{" "}
              {dayjs(nextDuty.data.slot_end_at).format("HH:mm")}
            </div>
            <div style={{ color: "#555", marginTop: 4 }}>{nextDuty.data.venue_name}</div>
            {nextDuty.data.teammates.length > 0 && (
              <div style={{ marginTop: 6, fontSize: 12, color: "#888" }}>
                同班：{nextDuty.data.teammates.map((t) => t.full_name).join("、")}
              </div>
            )}
          </div>
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无待值班次" />
        )}
      </Card>

      <Card size="small" title={`本月工时（${month}）`} style={{ marginBottom: 12 }}>
        {hours.isLoading ? (
          <Skeleton active paragraph={{ rows: 1 }} />
        ) : (
          <div style={{ display: "flex", gap: 24 }}>
            <Statistic title="实际完成" value={hoursOf(hours.data?.completed_minutes ?? 0)} suffix="h" />
            <Statistic title="排班平衡" value={hoursOf(hours.data?.balance_minutes ?? 0)} suffix="h" />
          </div>
        )}
      </Card>

      <Card
        size="small"
        title={
          <span>
            待处理{" "}
            {invitations.data && invitations.data.length > 0 && (
              <Badge count={invitations.data.length} />
            )}
          </span>
        }
      >
        <List
          size="small"
          locale={{ emptyText: "暂无待处理事项" }}
          dataSource={[
            ...(invitations.data ?? []).map((s) => ({
              key: `swap-${s.id}`,
              text: "收到换班邀请",
              tag: <Tag color="blue">待响应</Tag>,
              to: "/app/swaps",
            })),
            ...pendingLeaves.map((l) => ({
              key: `leave-${l.id}`,
              text: "请假申请审核中",
              tag: <Tag color="orange">待审核</Tag>,
              to: "/app/schedule",
            })),
          ]}
          renderItem={(item) => (
            <List.Item onClick={() => navigate(item.to)} style={{ cursor: "pointer" }}>
              <span>{item.text}</span>
              {item.tag}
            </List.Item>
          )}
        />
      </Card>
    </div>
  );
}
