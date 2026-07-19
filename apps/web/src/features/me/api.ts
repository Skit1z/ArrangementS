import { api } from "@/api/client";

export interface Teammate {
  full_name: string;
  class_name: string;
  phone: string;
}

export interface MyAssignment {
  assignment_id: string;
  slot_id: string;
  venue_name: string;
  slot_start_at: string;
  slot_end_at: string;
  credited_minutes: number;
  plan_status: string;
  execution_status: string;
  teammates: Teammate[];
  previous_shift: Teammate[];
  next_shift: Teammate[];
}

export interface NextDuty {
  assignment_id: string;
  venue_name: string;
  slot_start_at: string;
  slot_end_at: string;
  teammates: Teammate[];
  previous_shift: Teammate[];
  next_shift: Teammate[];
}

export interface MyHours {
  month: string;
  balance_minutes: number;
  completed_minutes: number;
  multiplier_extra_minutes?: number;
  leave_count?: number;
  swap_out_count?: number;
  absence_count?: number;
  status?: string;
  calculated: boolean;
  venues: { venue_id: string; completed_minutes: number }[];
}

export interface LeaveRequest {
  id: string;
  assignment_id: string;
  reason: string;
  is_emergency: boolean;
  status: string;
}

export interface SwapRequest {
  id: string;
  assignment_id: string;
  requester_person_id: string;
  mode: "targeted" | "open";
  target_person_id: string | null;
  selected_person_id: string | null;
  status: string;
  requester_name?: string | null;
  requester_phone?: string | null;
  venue_name?: string | null;
  slot_start_at?: string | null;
  slot_end_at?: string | null;
}

export interface AvailabilityRequest {
  id: string;
  person_id: string;
  start_at: string;
  end_at: string;
  reason: string;
  status: string;
}

export const meApi = {
  schedule: async () => (await api.get<MyAssignment[]>("/me/schedule")).data,
  nextDuty: async () => (await api.get<{ next: NextDuty | null }>("/me/next-duty")).data.next,
  hours: async (month: string) => (await api.get<MyHours>("/me/hours", { params: { month } })).data,

  leaves: async () => (await api.get<LeaveRequest[]>("/me/leave-requests")).data,
  createLeave: async (assignment_id: string, reason: string) =>
    (await api.post<LeaveRequest>("/me/leave-requests", { assignment_id, reason })).data,
  withdrawLeave: async (id: string) => (await api.post(`/me/leave-requests/${id}/withdraw`)).data,

  swaps: async () => (await api.get<SwapRequest[]>("/me/swap-requests")).data,
  invitations: async () => (await api.get<SwapRequest[]>("/me/swap-invitations")).data,
  openSwaps: async () => (await api.get<SwapRequest[]>("/swap-requests/open")).data,
  createOpenSwap: async (assignment_id: string, reason?: string) =>
    (await api.post<SwapRequest>("/me/swap-requests/open", { assignment_id, reason })).data,
  createTargetedSwap: async (assignment_id: string, target_person_id: string, reason?: string) =>
    (await api.post<SwapRequest>("/me/swap-requests/targeted", { assignment_id, target_person_id, reason })).data,
  acceptSwap: async (id: string) => (await api.post(`/me/swap-requests/${id}/accept`)).data,
  rejectSwap: async (id: string) => (await api.post(`/me/swap-requests/${id}/reject`)).data,
  applySwap: async (id: string) => (await api.post(`/me/swap-requests/${id}/apply`)).data,
  withdrawSwap: async (id: string) => (await api.post(`/me/swap-requests/${id}/withdraw`)).data,

  availabilityRequests: async () =>
    (await api.get<AvailabilityRequest[]>("/me/availability-requests")).data,
  createAvailabilityRequest: async (start_at: string, end_at: string, reason: string) =>
    (await api.post<AvailabilityRequest>("/me/availability-requests", { start_at, end_at, reason })).data,
  withdrawAvailabilityRequest: async (id: string) =>
    (await api.post(`/me/availability-requests/${id}/withdraw`)).data,

  overtime: async () => (await api.get<any[]>("/me/overtime")).data,
  createOvertime: async (venue_id: string, start_at: string, end_at: string, reason: string) =>
    (await api.post<any>("/me/overtime", { venue_id, start_at, end_at, reason })).data,
  peers: async () => (await api.get<Peer[]>("/me/peers")).data,
};

export interface Peer {
  id: string;
  full_name: string;
  class_name: string;
}

export const STATUS_LABEL: Record<string, string> = {
  pending: "待审核",
  approved: "已通过",
  rejected: "已拒绝",
  withdrawn: "已撤回",
  cancelled: "已取消",
  expired: "已失效",
  awaiting_target: "待对方响应",
  open_collecting: "公开征集中",
  pending_admin: "待管理员审核",
};

export const STATUS_COLOR: Record<string, string> = {
  pending: "orange",
  approved: "green",
  rejected: "red",
  withdrawn: "default",
  cancelled: "default",
  expired: "default",
  awaiting_target: "blue",
  open_collecting: "blue",
  pending_admin: "orange",
};

export function hoursOf(minutes: number): string {
  return (minutes / 60).toFixed(1);
}
