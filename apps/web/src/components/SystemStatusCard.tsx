import { useQuery } from "@tanstack/react-query";
import { Badge, Card, Col, Row, Tag } from "antd";
import {
  CheckCircleFilled,
  ClockCircleOutlined,
  CodeOutlined,
  DisconnectOutlined,
  HddOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import { api } from "@/api/client";
import { cardShadow, colors, radius } from "@/theme";

interface SystemStatus {
  status: string;
  backend_build_time: string;
  backend_start_time: string;
  uptime_seconds: number;
  uptime_formatted: string;
  env: string;
}

export function SystemStatusCard() {
  const { data, isError, isLoading, refetch } = useQuery<SystemStatus>({
    queryKey: ["system-status"],
    queryFn: async () => (await api.get("/system/status")).data,
    refetchInterval: 15000,
    retry: 2,
  });

  const isOnline = !isError && data?.status === "online";
  const frontendBuildTime = typeof __BUILD_TIME__ !== "undefined" ? __BUILD_TIME__ : "未提供";

  return (
    <Card
      size="small"
      title={
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ fontWeight: 600, fontSize: 14, color: colors.textPrimary }}>
            <HddOutlined style={{ marginRight: 6, color: colors.textTertiary }} />
            系统构建与存活状态
          </span>
          {isLoading ? (
            <Tag icon={<SyncOutlined spin />} color="processing">
              检测中
            </Tag>
          ) : isOnline ? (
            <Tag icon={<CheckCircleFilled />} color="success" style={{ padding: "2px 8px", borderRadius: 12 }}>
              后端运行正常 ({data?.uptime_formatted})
            </Tag>
          ) : (
            <Tag
              icon={<DisconnectOutlined />}
              color="error"
              style={{ padding: "2px 8px", borderRadius: 12, cursor: "pointer" }}
              onClick={() => refetch()}
            >
              后端离线 / 点击重试
            </Tag>
          )}
        </div>
      }
      bordered={false}
      style={{
        borderRadius: radius.card,
        boxShadow: cardShadow,
        marginBottom: 16,
        background: colors.bgContainer,
      }}
    >
      <Row gutter={[16, 12]} align="middle">
        <Col xs={24} sm={8}>
          <div style={{ fontSize: 12, color: "#8c8c8c", marginBottom: 4 }}>
            <CodeOutlined style={{ marginRight: 4 }} />
            前端构建时间
          </div>
          <div style={{ fontWeight: 600, fontSize: 13, color: "#262626" }}>
            {frontendBuildTime}
          </div>
        </Col>

        <Col xs={24} sm={8}>
          <div style={{ fontSize: 12, color: "#8c8c8c", marginBottom: 4 }}>
            <ClockCircleOutlined style={{ marginRight: 4 }} />
            后端构建/启动时间
          </div>
          <div style={{ fontWeight: 600, fontSize: 13, color: "#262626" }}>
            {data?.backend_build_time || (isLoading ? "连接中..." : "未在线")}
          </div>
        </Col>

        <Col xs={24} sm={8}>
          <div style={{ fontSize: 12, color: "#8c8c8c", marginBottom: 4 }}>
            <HddOutlined style={{ marginRight: 4 }} />
            后端存活状态
          </div>
          <div>
            {isOnline ? (
              <Badge status="success" text={<span style={{ fontWeight: 600, color: "#52c41a" }}>🟢 在线 (正常运行)</span>} />
            ) : (
              <Badge status="error" text={<span style={{ fontWeight: 600, color: "#ff4d4f" }}>🔴 离线 / 服务未响应</span>} />
            )}
          </div>
        </Col>
      </Row>
    </Card>
  );
}
