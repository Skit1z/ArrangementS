import axios from "axios";

function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp("(^|; )" + name + "=([^;]*)"));
  return match ? decodeURIComponent(match[2]) : null;
}

export const api = axios.create({
  baseURL: "/api/v1",
  withCredentials: true,
});

// 对非安全方法自动附带双提交 CSRF 令牌
api.interceptors.request.use((config) => {
  const method = (config.method || "get").toUpperCase();
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const token = readCookie("csrf_token");
    if (token) {
      config.headers = config.headers ?? {};
      config.headers["X-CSRF-Token"] = token;
    }
  }
  return config;
});

export interface ApiError {
  detail: string;
}

export function errorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = (err.response?.data as ApiError | undefined)?.detail;
    return detail || err.message;
  }
  return "未知错误";
}
