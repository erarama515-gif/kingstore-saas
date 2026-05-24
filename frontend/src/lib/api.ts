"use client";

import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from "axios";

const BASE = "/api/v1";

let accessToken: string | null = null;
let refreshToken: string | null = null;

export function setTokens(tokens: { access_token: string; refresh_token?: string }) {
  accessToken = tokens.access_token;
  if (tokens.refresh_token) refreshToken = tokens.refresh_token;
  if (typeof window !== "undefined") {
    localStorage.setItem("ks_access", tokens.access_token);
    if (tokens.refresh_token) localStorage.setItem("ks_refresh", tokens.refresh_token);
  }
}

export function clearTokens() {
  accessToken = null;
  refreshToken = null;
  if (typeof window !== "undefined") {
    localStorage.removeItem("ks_access");
    localStorage.removeItem("ks_refresh");
  }
}

export function loadTokens() {
  if (typeof window === "undefined") return;
  accessToken = localStorage.getItem("ks_access");
  refreshToken = localStorage.getItem("ks_refresh");
}

export const api: AxiosInstance = axios.create({
  baseURL: BASE,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((cfg: InternalAxiosRequestConfig) => {
  if (accessToken) cfg.headers.set("Authorization", `Bearer ${accessToken}`);
  return cfg;
});

let isRefreshing = false;
let queued: Array<(t: string | null) => void> = [];

api.interceptors.response.use(
  (r) => r,
  async (err: AxiosError) => {
    const original = err.config as InternalAxiosRequestConfig & { _retry?: boolean };
    if (
      err.response?.status === 401 &&
      !original._retry &&
      refreshToken &&
      original.url !== "/auth/refresh" &&
      original.url !== "/auth/login"
    ) {
      original._retry = true;
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          queued.push((token) => {
            if (!token) return reject(err);
            original.headers!.set("Authorization", `Bearer ${token}`);
            resolve(api(original));
          });
        });
      }
      isRefreshing = true;
      try {
        const res = await axios.post(
          `${BASE}/auth/refresh`,
          {},
          { headers: { Authorization: `Bearer ${refreshToken}` } },
        );
        const tokens = res.data.data?.tokens || res.data.tokens || res.data.data;
        setTokens(tokens);
        queued.forEach((cb) => cb(tokens.access_token));
        queued = [];
        original.headers!.set("Authorization", `Bearer ${tokens.access_token}`);
        return api(original);
      } catch (e) {
        queued.forEach((cb) => cb(null));
        queued = [];
        clearTokens();
        if (typeof window !== "undefined") window.location.href = "/login";
        return Promise.reject(e);
      } finally {
        isRefreshing = false;
      }
    }
    return Promise.reject(err);
  },
);

/* ----- Typed helpers ----- */

export type Paginated<T> = {
  data: T[];
  pagination: {
    page: number;
    per_page: number;
    total: number;
    pages: number;
    has_next: boolean;
    has_prev: boolean;
  };
};

export async function login(username: string, password: string, tenantSlug: string) {
  const res = await api.post("/auth/login", {
    username,
    password,
    tenant_slug: tenantSlug,
  });
  return res.data.data;
}

export async function signup(payload: Record<string, unknown>) {
  const res = await api.post("/auth/signup", payload);
  return res.data.data;
}

export async function me() {
  const res = await api.get("/auth/me");
  return res.data.data;
}

export async function logout() {
  try {
    await api.post("/auth/logout");
  } catch {
    /* ignore */
  } finally {
    clearTokens();
  }
}
