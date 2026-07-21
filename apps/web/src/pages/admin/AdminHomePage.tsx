import { useQuery } from "@tanstack/react-query";
import {
  CalendarOutlined,
  ClockCircleOutlined,
  NumberOutlined,
  RightOutlined,
  TeamOutlined,
} from "@ant-design/icons";
import { Button, Card, Col, Row, Statistic } from "antd";
import { useNavigate } from "react-router-dom";
import dayjs from "dayjs";
import { BeijingTimeBanner } from "@/components/BeijingTimeBanner";
import { CurrentDutyCard } from "@/components/CurrentDutyCard";
import { SystemStatusCard } from "@/components/SystemStatusCard";
import { adminApi } from "@/features/admin/api";

export default function AdminHomePage() {
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

  // 计算当前周数
  const currentWeekNum = currentSemester?.first_monday
    ? (() => {
        const diff = dayjs().diff(dayjs(currentSemester.first_monday), "day");
        const week = Math.floor(diff / 7) + 1;
        return week >= 1 && week <= (currentSemester.week_count || 20) ? week : null;
      })()
    : null;

  return (
    <div>
      {/* 显眼的实时北京时间横幅 */}
      <BeijingTimeBanner />

      {/* 系统构建与存活状态 Card */}
      <SystemStatusCard />

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
              title="当前周数"
              value={currentWeekNum ? `第 ${currentWeekNum} 周` : "—"}
              prefix={<NumberOutlined style={{ color: "#722ed1" }} />}
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
              onClick={() => navigate(currentWeekNum ? `/admin/timetables?week=${currentWeekNum}` : "/admin/timetables")}
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
