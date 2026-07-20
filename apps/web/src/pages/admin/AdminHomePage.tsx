import { useQuery } from "@tanstack/react-query";
import {
  CalendarOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  RightOutlined,
  TeamOutlined,
} from "@ant-design/icons";
import { Button, Card, Col, Row, Statistic, Typography } from "antd";
import { useNavigate } from "react-router-dom";
import { BeijingTimeBanner } from "@/components/BeijingTimeBanner";
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

  const semestersQuery = useQuery({
    queryKey: ["admin", "semesters"],
    queryFn: adminApi.semesters.list,
  });

  const activePeopleCount = (peopleQuery.data ?? []).filter((p) => p.status === "active").length;
  const currentSemester = (semestersQuery.data ?? []).find((s) => s.is_current);

  return (
    <div>
      {/* 显眼的实时北京时间横幅 */}
      <BeijingTimeBanner />

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
        <Col xs={24} sm={8} md={8}>
          <Card size="small" bordered={false} style={{ borderRadius: 10, boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
            <Statistic
              title="在岗人员"
              value={activePeopleCount}
              suffix="人"
              prefix={<TeamOutlined style={{ color: "#1890ff" }} />}
            />
          </Card>
        </Col>

        <Col xs={24} sm={8} md={8}>
          <Card size="small" bordered={false} style={{ borderRadius: 10, boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
            <Statistic
              title="当前学期"
              value={currentSemester?.name ?? "未设置"}
              prefix={<ClockCircleOutlined style={{ color: "#fa8c16" }} />}
            />
          </Card>
        </Col>

        <Col xs={24} sm={8} md={8}>
          <Card size="small" bordered={false} style={{ borderRadius: 10, boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
            <Statistic
              title="首周起始日期"
              value={currentSemester?.first_monday ?? "—"}
              prefix={<CheckCircleOutlined style={{ color: "#722ed1" }} />}
            />
          </Card>
        </Col>
      </Row>

      {/* 快捷导航：仅保留 查看本周值班表 和 查看本周无课表 */}
      <Card
        size="small"
        title={<span style={{ fontWeight: 600 }}>快捷管理操作</span>}
        bordered={false}
        style={{ borderRadius: 10, boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}
      >
        <Row gutter={[16, 16]}>
          <Col xs={24} sm={12}>
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
                <div style={{ fontWeight: 600, fontSize: 15 }}>查看本周值班表</div>
                <div style={{ fontSize: 12, opacity: 0.8 }}>进入周排班大盘查看及调整值班安排</div>
              </div>
              <RightOutlined />
            </Button>
          </Col>

          <Col xs={24} sm={12}>
            <Button
              block
              size="large"
              icon={<CalendarOutlined />}
              onClick={() => navigate("/admin/timetables")}
              style={{ height: 60, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "space-between" }}
            >
              <div style={{ textAlign: "left" }}>
                <div style={{ fontWeight: 600, fontSize: 15 }}>查看本周无课表</div>
                <div style={{ fontSize: 12, opacity: 0.8 }}>查看全员课程安排及空闲时间段</div>
              </div>
              <RightOutlined />
            </Button>
          </Col>
        </Row>
      </Card>
    </div>
  );
}
