import {
  CalendarOutlined,
  FormOutlined,
  HomeOutlined,
} from "@ant-design/icons";
import { Layout } from "antd";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { colors } from "@/theme";

// 移动端底部导航
const tabs = [
  { key: "/app/home", icon: <HomeOutlined />, label: "首页" },
  { key: "/app/schedule", icon: <CalendarOutlined />, label: "我的排班" },
  { key: "/app/requests", icon: <FormOutlined />, label: "申请中心" },
];

export default function UserLayout() {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <Layout style={{ minHeight: "100vh", maxWidth: 640, margin: "0 auto", background: colors.bgPage }}>
      <Layout.Content style={{ padding: "16px 16px 80px" }}>
        <Outlet />
      </Layout.Content>
      <div
        style={{
          position: "fixed",
          bottom: 0,
          left: 0,
          right: 0,
          maxWidth: 640,
          margin: "0 auto",
          display: "flex",
          borderTop: `1px solid ${colors.borderLight}`,
          background: colors.bgContainer,
        }}
      >
        {tabs.map((t) => {
          const active = location.pathname === t.key;
          return (
            <div
              key={t.key}
              onClick={() => navigate(t.key)}
              style={{
                flex: 1,
                textAlign: "center",
                padding: "8px 0 6px",
                color: active ? colors.primary : colors.textTertiary,
                cursor: "pointer",
              }}
            >
              <div style={{ fontSize: 20, lineHeight: 1.4 }}>{t.icon}</div>
              <div style={{ fontSize: 12, fontWeight: active ? 600 : 400 }}>{t.label}</div>
            </div>
          );
        })}
      </div>
    </Layout>
  );
}
