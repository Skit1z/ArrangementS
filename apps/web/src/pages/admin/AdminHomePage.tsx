import { useQuery } from "@tanstack/react-query";
import {
  CalendarOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  RightOutlined,
  SafetyCertificateOutlined,
  ShopOutlined,
  TeamOutlined,
} from "@ant-design/icons";
import { Button, Card, Col, Row, Statistic, Typography } from "antd";
import { useNavigate } from "react-router-dom";
import { CurrentDutyCard } from "@/components/CurrentDutyCard";
import { adminApi } from "@/features/admin/api";
import { useAuth } from "@/stores/auth";

export default function AdminHomePage() {
  const user = useAuth((s) => s.user);
  const navigate = useNavigate();

  const peopleQuery = useQuery({
    queryKey: ["admin", "people"],
    queryFn: adminApi.people.list,
  });

  const venuesQuery = useQuery({
    queryKey: ["admin", "venues"],
    queryFn: adminApi.venues.list,
  });

  const semestersQuery = useQuery({
    queryKey: ["admin", "semesters"],
    queryFn: adminApi.semesters.list,
  });

  const activePeopleCount = (peopleQuery.data ?? []).filter((p) => p.status === "active").length;
  const activeVenuesCount = (venuesQuery.data ?? []).filter((v) => v.is_active).length;
  const currentSemester = (semestersQuery.data ?? []).find((s) => s.is_current);

  return (
    <div>
      <div style={{ marginBottom: 20, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <Typography.Title level={3} style={{ margin: 0, fontWeight: 600 }}>
            管理员控制台
          </Typography.Title>
          <Typography.Text type="secondary">
            欢迎回来，{user?.username}！实时关注今天与本周的值班动态。
          </Typography.Text>
        </div>
      </div>

      {/* 实时值班人员与联系方式 Card */}
      <CurrentDutyCard />

      {/* 统计指标卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 20 }}>
        <Col xs={24} sm={12} md={6}>
          <Card size="small" bordered={false} style={{ borderRadius: 10, boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
            <Statistic
              title="在册活跃人员"
              value={activePeopleCount}
              suffix="人"
              prefix={<TeamOutlined style={{ color: "#1890ff" }} />}
            />
          </Card>
        </Col>

        <Col xs={24} sm={12} md={6}>
          <Card size="small" bordered={false} style={{ borderRadius: 10, boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
            <Statistic
              title="活跃值班场地"
              value={activeVenuesCount}
              suffix="个"
              prefix={<ShopOutlined style={{ color: "#52c41a" }} />}
            />
          </Card>
        </Col>

        <Col xs={24} sm={12} md={6}>
          <Card size="small" bordered={false} style={{ borderRadius: 10, boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
            <Statistic
              title="当前学期"
              value={currentSemester?.name ?? "未设置"}
              prefix={<ClockCircleOutlined style={{ color: "#fa8c16" }} />}
            />
          </Card>
        </Col>

        <Col xs={24} sm={12} md={6}>
          <Card size="small" bordered={false} style={{ borderRadius: 10, boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
            <Statistic
              title="首周起始日期"
              value={currentSemester?.first_monday ?? "—"}
              prefix={<CheckCircleOutlined style={{ color: "#722ed1" }} />}
            />
          </Card>
        </Col>
      </Row>

      {/* 快捷导航与常规工具 */}
      <Card
        size="small"
        title={<span style={{ fontWeight: 600 }}>快捷管理操作</span>}
        bordered={false}
        style={{ borderRadius: 10, boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}
      >
        <Row gutter={[16, 16]}>
          <Col xs={24} sm={12} md={6}>
            <Button
              block
              size="large"
              type="primary"
              ghost
              icon={<CalendarOutlined />}
              onClick={() => navigate("/admin/schedule")}
              style={{ height: 60, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "space-between" }}
            >
              <div style={{ textAlign: "left" }}>
                <div style={{ fontWeight: 600, fontSize: 14 }}>周排班大盘</div>
                <div style={{ fontSize: 11, opacity: 0.8 }}>智能排班与班次调整</div>
              </div>
              <RightOutlined />
            </Button>
          </Col>

          <Col xs={24} sm={12} md={6}>
            <Button
              block
              size="large"
              icon={<SafetyCertificateOutlined />}
              onClick={() => navigate("/admin/review")}
              style={{ height: 60, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "space-between" }}
            >
              <div style={{ textAlign: "left" }}>
                <div style={{ fontWeight: 600, fontSize: 14 }}>审核中心</div>
                <div style={{ fontSize: 11, opacity: 0.8 }}>处理请假与换班申请</div>
              </div>
              <RightOutlined />
            </Button>
          </Col>

          <Col xs={24} sm={12} md={6}>
            <Button
              block
              size="large"
              icon={<TeamOutlined />}
              onClick={() => navigate("/admin/people")}
              style={{ height: 60, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "space-between" }}
            >
              <div style={{ textAlign: "left" }}>
                <div style={{ fontWeight: 600, fontSize: 14 }}>人员管理</div>
                <div style={{ fontSize: 11, opacity: 0.8 }}>录入人员与导入白名单</div>
              </div>
              <RightOutlined />
            </Button>
          </Col>

          <Col xs={24} sm={12} md={6}>
            <Button
              block
              size="large"
              icon={<CalendarOutlined />}
              onClick={() => navigate("/admin/timetables")}
              style={{ height: 60, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "space-between" }}
            >
              <div style={{ textAlign: "left" }}>
                <div style={{ fontWeight: 600, fontSize: 14 }}>全员无课表</div>
                <div style={{ fontSize: 11, opacity: 0.8 }}>按周筛选与导出 Excel</div>
              </div>
              <RightOutlined />
            </Button>
          </Col>
        </Row>
      </Card>
    </div>
  );
}
