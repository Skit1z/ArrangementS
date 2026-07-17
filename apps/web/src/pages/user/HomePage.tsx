import { Card, Typography } from "antd";

import { useAuth } from "@/stores/auth";

export default function HomePage() {
  const user = useAuth((s) => s.user);
  return (
    <div>
      <Typography.Title level={4}>你好，{user?.username}</Typography.Title>
      <Card size="small" style={{ marginBottom: 12 }} title="下一次值班">
        <Typography.Text type="secondary">暂无数据（发布排班后显示）</Typography.Text>
      </Card>
      <Card size="small" style={{ marginBottom: 12 }} title="本月统计工时">
        <Typography.Text type="secondary">在“工时”页查看</Typography.Text>
      </Card>
      <Card size="small" title="待处理">
        <Typography.Text type="secondary">换班邀请 / 请假审核状态</Typography.Text>
      </Card>
    </div>
  );
}
