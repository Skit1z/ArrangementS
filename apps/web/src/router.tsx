import { createBrowserRouter, Navigate } from "react-router-dom";

import ProtectedRoute from "@/components/ProtectedRoute";
import AdminLayout from "@/layouts/AdminLayout";
import UserLayout from "@/layouts/UserLayout";
import LoginPage from "@/pages/LoginPage";
import Placeholder from "@/pages/Placeholder";
import PeoplePage from "@/pages/admin/PeoplePage";
import SchedulePage from "@/pages/admin/SchedulePage";
import AvailabilityPage from "@/pages/user/AvailabilityPage";
import HomePage from "@/pages/user/HomePage";
import HoursPage from "@/pages/user/HoursPage";
import MySchedulePage from "@/pages/user/MySchedulePage";
import SwapsPage from "@/pages/user/SwapsPage";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    element: <ProtectedRoute role="admin" />,
    children: [
      {
        path: "/admin",
        element: <AdminLayout />,
        children: [
          { index: true, element: <Navigate to="/admin/schedule" replace /> },
          { path: "schedule", element: <SchedulePage /> },
          { path: "people", element: <PeoplePage /> },
          { path: "venues", element: <Placeholder title="场地与任务" /> },
          { path: "statistics", element: <Placeholder title="月度统计" /> },
          { path: "settings", element: <Placeholder title="系统配置" /> },
        ],
      },
    ],
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        path: "/app",
        element: <UserLayout />,
        children: [
          { index: true, element: <Navigate to="/app/home" replace /> },
          { path: "home", element: <HomePage /> },
          { path: "schedule", element: <MySchedulePage /> },
          { path: "availability", element: <AvailabilityPage /> },
          { path: "swaps", element: <SwapsPage /> },
          { path: "hours", element: <HoursPage /> },
        ],
      },
    ],
  },
  { path: "*", element: <Navigate to="/login" replace /> },
]);
