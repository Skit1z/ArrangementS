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
import { adminApi, type Semester } from "@/features/admin/api";

interface CurrentWeek {
  week: number;
  label: string;
}

/**
 * 计算当前所在的"周次"（包含教学周和寒暑假）。
 * - 教学周：第 1 ~ week_count 周
 * - 寒暑假：学期结束后的 1, 2, 3... 周，标"寒假第N周"/"暑假第N周"
 * 不可计算时返回 null。
 */
function computeCurrentWeek(semesters: Semester[]): CurrentWeek | null {
  if (semesters.length === 0) return null;
  const today = dayjs();
  const todayDate = today.startOf("day");

  const sorted = [...semesters].sort((a, b) =>
    a.first_monday.localeCompare(b.first_monday),
  );

  // 1) 命中 is_current 的学期
  const current = sorted.find((s) => s.is_current);
  if (current) {
    const firstMonday = dayjs(current.first_monday);
    const lastMonday = firstMonday.add((current.week_count ?? 20) - 1, "week");
    if (
      todayDate.isSame(firstMonday) ||
      (todayDate.isAfter(firstMonday) && todayDate.isBefore(lastMonday.add(1, "day")))
    ) {
      const diff = todayDate.diff(firstMonday, "day");
      const week = Math.floor(diff / 7) + 1;
      return { week, label: `第 ${week} 周` };
    }
  }

  // 2) 是否处于某学期结束之后的寒暑假
  const endedSemesters = sorted.filter((s) => {
    const semEnd = dayjs(s.first_monday).add(s.week_count, "week");
    return todayDate.isAfter(semEnd.subtract(1, "day"));
  });
  if (endedSemesters.length > 0) {
    const latest = endedSemesters[endedSemesters.length - 1];
    const semEnd = dayjs(latest.first_monday).add(latest.week_count, "week");
    if (todayDate.isAfter(semEnd.subtract(1, "day"))) {
      const diff = todayDate.diff(semEnd, "day");
      if (diff >= 0) {
        const vacationWeek = Math.floor(diff / 7) + 1;
        // 学期结束月份决定是寒假还是暑假
        const semEndMonth = semEnd.month() + 1;
        const isWinter = [1, 2, 3, 11, 12].includes(semEndMonth);
        const name = isWinter ? "寒假" : "暑假";
        return { week: vacationWeek, label: `${name}第 ${vacationWeek} 周` };
      }
    }
  }

  return null;
}

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
  const currentWeek = computeCurrentWeek(semestersQuery.data ?? []);

  return (
    <div>
      {/* 显眼的实时北京时间横幅 */}
      <BeijingTimeBanner />

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
              value={currentWeek?.label ?? "—"}
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
        style={{ borderRadius: 10, boxShadow: "0 2px 8px rgba(0,0,0,0.04)", marginBottom: 20 }}
      >
        <Row gutter={[16, 16]}>
          <Col xs={24} sm={12}>
            <Button
              block
              size="large"
              icon={<CalendarOutlined />}
              onClick={() => navigate("/admin/schedule")}
              style={{
                height: 60,
                borderRadius: 8,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                background: "#fff",
              }}
            >
              <div style={{ textAlign: "left" }}>
                <div style={{ fontWeight: 600, fontSize: 15, color: "#262626" }}>查看本周值班表</div>
                <div style={{ fontSize: 12, opacity: 0.7, color: "#595959" }}>进入周排班大盘查看及调整值班安排</div>
              </div>
              <RightOutlined style={{ color: "#8c8c8c" }} />
            </Button>
          </Col>

          <Col xs={24} sm={12}>
            <Button
              block
              size="large"
              icon={<CalendarOutlined />}
              onClick={() => navigate(currentWeek ? `/admin/timetables?week=${currentWeek.week}` : "/admin/timetables")}
              style={{
                height: 60,
                borderRadius: 8,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                background: "#fff",
              }}
            >
              <div style={{ textAlign: "left" }}>
                <div style={{ fontWeight: 600, fontSize: 15, color: "#262626" }}>查看本周无课表</div>
                <div style={{ fontSize: 12, opacity: 0.7, color: "#595959" }}>查看全员课程安排及空闲时间段</div>
              </div>
              <RightOutlined style={{ color: "#8c8c8c" }} />
            </Button>
          </Col>
        </Row>
      </Card>

      {/* 系统构建与存活状态 - 移至最后一栏 */}
      <SystemStatusCard />
    </div>
  );
}
