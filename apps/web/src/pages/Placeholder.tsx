import { Card, Empty } from "antd";

export default function Placeholder({ title }: { title: string }) {
  return (
    <Card title={title}>
      <Empty description="该模块即将上线（后端 API 已就绪）" />
    </Card>
  );
}
