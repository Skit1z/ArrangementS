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
import DutyRosterPage from "@/pages/admin/DutyRosterPage";
import VenuesPage from "@/pages/admin/VenuesPage";
import AdminOvertimePage from "@/pages/admin/AdminOvertimePage";
import AdminHomePage from "@/pages/admin/AdminHomePage";
import HomePage from "@/pages/user/HomePage";
import HoursPage from "@/pages/user/HoursPage";
import MySchedulePage from "@/pages/user/MySchedulePage";
import UploadTimetablePage from "@/pages/user/UploadTimetablePage";
import RequestsPage from "@/pages/user/RequestsPage";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    element: <ProtectedRoute role="admin" />,
    children: [
      {
        path: "/admin",
        element: <AdminLayout />,
        children: [
          { index: true, element: <Navigate to="/admin/home" replace /> },
          { path: "home", element: <AdminHomePage /> },
          { path: "schedule", element: <SchedulePage /> },
          { path: "roster", element: <DutyRosterPage /> },
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
          { path: "requests", element: <RequestsPage /> },
          { path: "availability", element: <Navigate to="/app/requests?tab=availability" replace /> },
          { path: "swaps", element: <Navigate to="/app/requests?tab=swaps" replace /> },
          { path: "overtime", element: <Navigate to="/app/requests?tab=overtime" replace /> },
          { path: "hours", element: <HoursPage /> },
        ],
      },
    ],
  },
  { path: "*", element: <Navigate to="/login" replace /> },
]);
