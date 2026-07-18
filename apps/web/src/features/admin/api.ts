import { api } from "@/api/client";

// --- 场地 ---
export type VenueType = "fixed_shift" | "event_based";

export interface Venue {
  id: string;
  name: string;
  code: string;
  venue_type: VenueType;
  address: string | null;
  default_required_people: number;
  default_prep_minutes: number;
  default_cleanup_minutes: number;
  sort_order: number;
  is_active: boolean;
}

export interface VenueCreate {
  name: string;
  code: string;
  venue_type: VenueType;
  address?: string;
  default_required_people?: number;
  default_prep_minutes?: number;
  default_cleanup_minutes?: number;
  sort_order?: number;
  description?: string;
}

export interface VenueUpdate {
  name?: string;
  address?: string;
  default_required_people?: number;
  default_prep_minutes?: number;
  default_cleanup_minutes?: number;
  sort_order?: number;
  description?: string;
}

// --- 班次模板 ---
export interface ShiftTemplate {
  id?: string;
  name: string;
  start_time: string; // HH:mm:ss
  end_time: string;
  credited_minutes: number;
  weekday_required_people: number;
  weekend_required_people: number;
  is_active: boolean;
}

// --- 任务 ---
export type TaskStatus =
  | "draft"
  | "confirmed"
  | "scheduled"
  | "executing"
  | "completed"
  | "cancelled";

export interface TaskListItem {
  id: string;
  venue_id: string;
  venue_name: string;
  title: string;
  booking_start_at: string;
  booking_end_at: string;
  prep_minutes: number;
  cleanup_minutes: number;
  duty_start_at: string;
  duty_end_at: string;
  required_people: number;
  is_temporary: boolean;
  status: TaskStatus;
  version: number;
  organization: string | null;
  contact_name: string | null;
  contact_phone: string | null;
}

export interface TaskCreate {
  venue_id: string;
  title: string;
  booking_start_at: string;
  booking_end_at: string;
  prep_minutes?: number;
  cleanup_minutes?: number;
  required_people?: number;
  is_temporary?: boolean;
  organization?: string;
  contact_name?: string;
  contact_phone?: string;
  requirements?: string;
  notes?: string;
}

export interface TaskUpdate extends Partial<Omit<TaskCreate, "venue_id">> {
  expected_version?: number;
}

export interface TaskHoursPreview {
  raw_minutes: number;
  weighted_minutes_before_round: number;
  credited_minutes: number;
  segments: {
    start_at: string;
    end_at: string;
    minutes: number;
    multiplier: number;
    rule_name: string | null;
  }[];
}

// --- 统计 ---
export interface MonthlySummary {
  person_id: string;
  person_name: string | null;
  student_no: string | null;
  class_name: string | null;
  balance_minutes: number;
  completed_minutes: number;
  multiplier_extra_minutes: number;
  leave_count: number;
  swap_out_count: number;
  replacement_count: number;
  absence_count: number;
  status: string;
}

export interface PersonMonthlyDetail extends MonthlySummary {
  venues: {
    venue_id: string;
    venue_name: string;
    completed_minutes: number;
    balance_minutes: number;
  }[];
}

export interface AdjustmentIn {
  person_id: string;
  minutes_delta: number;
  affect_balance: boolean;
  reason: string;
}

// --- 倍率规则 ---
export interface MultiplierRule {
  id: string;
  name: string;
  start_time: string;
  end_time: string;
  multiplier: string; // Decimal 字符串
  venue_id: string | null;
  weekdays: number[] | null;
  priority: number;
  is_active: boolean;
}

export interface MultiplierRuleIn {
  name: string;
  start_time: string;
  end_time: string;
  multiplier: string;
  venue_id?: string | null;
  weekdays?: number[] | null;
  priority?: number;
  is_active?: boolean;
}

// --- 特殊日期 ---
export type DayType = "workday" | "weekend_rule" | "closed" | "custom";

export interface SpecialDate {
  id: string;
  date: string;
  day_type: DayType;
  custom_required_people: number | null;
  reason: string | null;
  source: string;
}

export interface SpecialDateIn {
  date: string;
  day_type: DayType;
  custom_required_people?: number | null;
  reason?: string;
}

export interface HolidaySyncItem {
  date: string;
  day_type: DayType;
  reason: string | null;
  is_off_day?: boolean;
  status?: "new" | "same" | "conflict";
  existing_day_type?: string | null;
}

// --- 审计日志 ---
export interface AuditLog {
  id: string;
  actor_user_id: string | null;
  actor_username: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  reason: string | null;
  created_at: string;
}

export const adminApi = {
  // 场地
  venues: {
    list: async () => (await api.get<Venue[]>("/venues")).data,
    create: async (payload: VenueCreate) => (await api.post<Venue>("/venues", payload)).data,
    update: async (id: string, payload: VenueUpdate) =>
      (await api.patch<Venue>(`/venues/${id}`, payload)).data,
    disable: async (id: string) => (await api.post(`/venues/${id}/disable`)).data,
  },

  // 班次模板（仅固定班次场地，整体替换）
  shiftTemplates: {
    get: async (venueId: string) =>
      (await api.get<ShiftTemplate[]>(`/venues/${venueId}/shift-templates`)).data,
    replace: async (venueId: string, templates: ShiftTemplate[]) =>
      (await api.put<ShiftTemplate[]>(`/venues/${venueId}/shift-templates`, templates)).data,
  },

  // 任务
  tasks: {
    list: async (params?: { venue_id?: string; status?: TaskStatus; from?: string; to?: string; include_cancelled?: boolean }) =>
      (await api.get<TaskListItem[]>("/venue-tasks", { params })).data,
    create: async (payload: TaskCreate) => (await api.post<TaskListItem>("/venue-tasks", payload)).data,
    update: async (id: string, payload: TaskUpdate) =>
      (await api.patch<TaskListItem>(`/venue-tasks/${id}`, payload)).data,
    cancel: async (id: string) => (await api.post(`/venue-tasks/${id}/cancel`)).data,
    previewHours: async (id: string) =>
      (await api.get<TaskHoursPreview>(`/venue-tasks/${id}/hours-preview`)).data,
  },

  // 统计
  statistics: {
    monthly: async (month: string) =>
      (await api.get<MonthlySummary[]>(`/statistics/monthly/${month}`)).data,
    personMonthly: async (month: string, personId: string) =>
      (await api.get<PersonMonthlyDetail>(`/statistics/monthly/${month}/people/${personId}`)).data,
    recalculate: async (month: string) =>
      (await api.post<{ message: string }>(`/statistics/monthly/${month}/recalculate`)).data,
    lock: async (month: string) =>
      (await api.post<{ message: string }>(`/statistics/monthly/${month}/lock`)).data,
    adjust: async (month: string, payload: AdjustmentIn) =>
      (await api.post<{ message: string }>(`/statistics/monthly/${month}/adjustments`, payload)).data,
    // 导出走浏览器导航（带 cookie），不经过 axios
    exportUrl: (month: string) => `/api/v1/statistics/monthly/${month}/export`,
  },

  // 倍率规则
  multipliers: {
    list: async () => (await api.get<MultiplierRule[]>("/multiplier-rules")).data,
    create: async (payload: MultiplierRuleIn) =>
      (await api.post<MultiplierRule>("/multiplier-rules", payload)).data,
    update: async (id: string, payload: MultiplierRuleIn) =>
      (await api.patch<MultiplierRule>(`/multiplier-rules/${id}`, payload)).data,
    disable: async (id: string) => (await api.post(`/multiplier-rules/${id}/disable`)).data,
  },

  // 特殊日期
  specialDates: {
    list: async (year?: number) =>
      (await api.get<SpecialDate[]>("/special-dates", { params: { year } })).data,
    create: async (payload: SpecialDateIn) =>
      (await api.post<SpecialDate>("/special-dates", payload)).data,
    sync: async (year: number, data?: object) =>
      (await api.post<HolidaySyncItem[]>("/special-dates/sync", { year, data })).data,
    confirmSync: async (items: HolidaySyncItem[]) =>
      (await api.post<{ message: string }>("/special-dates/sync/confirm", { items })).data,
  },

  // 审计日志
  auditLogs: {
    list: async (limit = 100) =>
      (await api.get<AuditLog[]>("/audit-logs", { params: { limit } })).data,
  },
};

// --- 展示常量 ---
export const VENUE_TYPE_LABEL: Record<VenueType, string> = {
  fixed_shift: "固定班次",
  event_based: "按任务",
};

export const TASK_STATUS_LABEL: Record<TaskStatus, string> = {
  draft: "草稿",
  confirmed: "已确认",
  scheduled: "已排班",
  executing: "执行中",
  completed: "已完成",
  cancelled: "已取消",
};

export const TASK_STATUS_COLOR: Record<TaskStatus, string> = {
  draft: "default",
  confirmed: "blue",
  scheduled: "cyan",
  executing: "processing",
  completed: "green",
  cancelled: "red",
};

export const DAY_TYPE_LABEL: Record<DayType, string> = {
  workday: "调休工作日",
  weekend_rule: "节假日/周末",
  closed: "停班",
  custom: "自定义人数",
};

export const MONTHLY_STATUS_LABEL: Record<string, string> = {
  calculating: "计算中",
  draft: "草稿",
  confirmed: "已确认",
  locked: "已锁定",
};
