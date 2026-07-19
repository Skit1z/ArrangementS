import { createBrowserRouter, Navigate } from "react-router-dom";

import ProtectedRoute from "@/components/ProtectedRoute";
import AdminLayout from "@/layouts/AdminLayout";
import UserLayout from "@/layouts/UserLayout";
import LoginPage from "@/pages/LoginPage";
import PeoplePage from "@/pages/admin/PeoplePage";
import ReviewCenterPage from "@/pages/admin/ReviewCenterPage";
import SchedulePage from "@/pages/admin/SchedulePage";
import SettingsPage from "@/pages/admin/SettingsPage";
import StatisticsPage from "@/pages/admin/StatisticsPage";
import TasksPage from "@/pages/admin/TasksPage";
import TimetablesPage from "@/pages/admin/TimetablesPage";
import VenuesPage from "@/pages/admin/VenuesPage";
import AdminOvertimePage from "@/pages/admin/AdminOvertimePage";
import AvailabilityPage from "@/pages/user/AvailabilityPage";
import HomePage from "@/pages/user/HomePage";
import HoursPage from "@/pages/user/HoursPage";
import MySchedulePage from "@/pages/user/MySchedulePage";
import SwapsPage from "@/pages/user/SwapsPage";
import OvertimePage from "@/pages/user/OvertimePage";
import UploadTimetablePage from "@/pages/user/UploadTimetablePage";

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
          { path: "review", element: <ReviewCenterPage /> },
          { path: "timetables", element: <TimetablesPage /> },
          { path: "venues", element: <VenuesPage /> },
          { path: "tasks", element: <TasksPage /> },
          { path: "overtime", element: <AdminOvertimePage /> },
          { path: "statistics", element: <StatisticsPage /> },
          { path: "settings", element: <SettingsPage /> },
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
          { path: "timetable", element: <UploadTimetablePage /> },
          { path: "availability", element: <AvailabilityPage /> },
          { path: "swaps", element: <SwapsPage /> },
          { path: "overtime", element: <OvertimePage /> },
          { path: "hours", element: <HoursPage /> },
        ],
      },
    ],
  },
  { path: "*", element: <Navigate to="/login" replace /> },
]);
