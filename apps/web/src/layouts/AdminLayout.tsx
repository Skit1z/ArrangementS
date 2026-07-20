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
      <Layout.Sider theme="light" breakpoint="lg" collapsedWidth="0">
        <div style={{ height: 48, margin: 16, fontWeight: 600 }}>排班管理后台</div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={items}
          onClick={(e) => navigate(e.key)}
        />
      </Layout.Sider>
      <Layout>
        <Layout.Header style={{ background: "#fff", display: "flex", justifyContent: "flex-end", alignItems: "center", paddingRight: 24 }}>
          <span style={{ marginRight: 16 }}>{user?.username}</span>
          <Button icon={<LogoutOutlined />} onClick={() => logout().then(() => navigate("/login"))}>
            退出
          </Button>
        </Layout.Header>
        <Layout.Content style={{ margin: 16 }}>
          <Outlet />
        </Layout.Content>
      </Layout>
    </Layout>
  );
}
