import { Spin } from "antd";
import { useEffect } from "react";
import { Navigate, Outlet } from "react-router-dom";

import { type Role, useAuth } from "@/stores/auth";

export default function ProtectedRoute({ role }: { role?: Role }) {
  const { user, loading, fetchMe } = useAuth();

  useEffect(() => {
    if (!user) fetchMe();
  }, [user, fetchMe]);

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", paddingTop: 120 }}>
        <Spin size="large" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  if (role && user.role !== role) {
    return <Navigate to={user.role === "admin" ? "/admin/schedule" : "/app/home"} replace />;
  }
  return <Outlet />;
}
