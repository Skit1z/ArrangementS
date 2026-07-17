import { create } from "zustand";

import { api } from "@/api/client";

export type Role = "admin" | "user";

export interface CurrentUser {
  id: string;
  username: string;
  role: Role;
  is_active: boolean;
}

interface AuthState {
  user: CurrentUser | null;
  loading: boolean;
  fetchMe: () => Promise<void>;
  login: (username: string, password: string) => Promise<CurrentUser>;
  logout: () => Promise<void>;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  loading: true,
  fetchMe: async () => {
    set({ loading: true });
    try {
      const { data } = await api.get<CurrentUser>("/auth/me");
      set({ user: data, loading: false });
    } catch {
      set({ user: null, loading: false });
    }
  },
  login: async (username, password) => {
    const { data } = await api.post<CurrentUser>("/auth/login", { username, password });
    // 登录后已确知身份，结束 loading，避免受保护路由一直转圈
    set({ user: data, loading: false });
    return data;
  },
  logout: async () => {
    await api.post("/auth/logout");
    set({ user: null, loading: false });
  },
}));
