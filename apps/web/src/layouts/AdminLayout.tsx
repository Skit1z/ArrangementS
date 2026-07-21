import {
  AuditOutlined,
  CalendarOutlined,
  HomeOutlined,
  LogoutOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  ShopOutlined,
  TeamOutlined,
} from "@ant-design/icons";
import { Button, Layout, Menu } from "antd";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "@/stores/auth";
import { colors } from "@/theme";

const items = [
  { key: "/admin/home", icon: <HomeOutlined />, label: "首页" },
  { key: "/admin/schedule", icon: <CalendarOutlined />, label: "排班" },
  { key: "/admin/people", icon: <TeamOutlined />, label: "人员" },
  { key: "/admin/timetables", icon: <CalendarOutlined />, label: "全员课表" },
  { key: "/admin/venues", icon: <ShopOutlined />, label: "场地管理" },
  { key: "/admin/tasks", icon: <ShopOutlined />, label: "任务管理" },
  { key: "/admin/review", icon: <SafetyCertificateOutlined />, label: "审核中心" },
  { key: "/admin/overtime", icon: <AuditOutlined />, label: "加班审批" },
  { key: "/admin/statistics", icon: <AuditOutlined />, label: "统计" },
  { key: "/admin/settings", icon: <SettingOutlined />, label: "系统配置" },
];

export default function AdminLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const logout = useAuth((s) => s.logout);
  const user = useAuth((s) => s.user);

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Layout.Sider
        theme="light"
        breakpoint="lg"
        collapsedWidth="0"
        style={{ borderRight: `1px solid ${colors.borderLight}` }}
      >
        <div
          style={{
            height: 56,
            display: "flex",
            alignItems: "center",
            padding: "0 20px",
            fontWeight: 600,
            fontSize: 15,
            color: colors.textPrimary,
            borderBottom: `1px solid ${colors.borderLight}`,
            letterSpacing: 0.5,
          }}
        >
          排班管理后台
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={items}
          onClick={(e) => navigate(e.key)}
          style={{ borderInlineEnd: "none", padding: "8px 8px" }}
        />
      </Layout.Sider>
      <Layout>
        <Layout.Header
          style={{
            background: colors.bgContainer,
            display: "flex",
            justifyContent: "flex-end",
            alignItems: "center",
            paddingRight: 24,
            borderBottom: `1px solid ${colors.borderLight}`,
            height: 56,
            lineHeight: "normal",
          }}
        >
          <span style={{ marginRight: 16, color: colors.textSecondary, fontSize: 13 }}>{user?.username}</span>
          <Button icon={<LogoutOutlined />} onClick={() => logout().then(() => navigate("/login"))}>
            退出
          </Button>
        </Layout.Header>
        <Layout.Content style={{ padding: "20px 24px", maxWidth: 1280, width: "100%", margin: "0 auto" }}>
          <Outlet />
        </Layout.Content>
      </Layout>
    </Layout>
  );
}
