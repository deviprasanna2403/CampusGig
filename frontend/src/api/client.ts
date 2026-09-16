/**
 * The one HTTP client every API module goes through.
 *
 * Responsibilities (matched to the verified backend contract):
 * - Base URL from VITE_API_BASE_URL ("" in dev → Vite's /api proxy).
 * - Bearer token from the token store on every request.
 * - 401 handling: single-flight refresh (SimpleJWT rotates BOTH tokens on
 *   refresh — the new refresh must be stored), then replay queued requests.
 *   If the refresh itself fails (expired/blacklisted), clear the session and
 *   notify listeners so the router can send the user to /login.
 * - Errors: normalize the backend's {"success":false,"error":{...}} envelope
 *   into ApiError with .status/.code/.details.
 */

import axios, { AxiosError, type AxiosRequestConfig } from "axios";
import type { ApiErrorDetails, ErrorEnvelope, RefreshResponse } from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export const TOKEN_KEYS = {
  access: "cg.access",
  refresh: "cg.refresh",
  user: "cg.user",
} as const;

export const tokenStore = {
  get access() {
    return localStorage.getItem(TOKEN_KEYS.access);
  },
  get refresh() {
    return localStorage.getItem(TOKEN_KEYS.refresh);
  },
  set(access: string, refresh: string) {
    localStorage.setItem(TOKEN_KEYS.access, access);
    localStorage.setItem(TOKEN_KEYS.refresh, refresh);
  },
  clear() {
    localStorage.removeItem(TOKEN_KEYS.access);
    localStorage.removeItem(TOKEN_KEYS.refresh);
    localStorage.removeItem(TOKEN_KEYS.user);
  },
};

export class ApiError extends Error {
  status: number;
  code: number;
  details: ApiErrorDetails | null;

  constructor(status: number, code: number, message: string, details: ApiErrorDetails | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** First field-level message, for inline form errors. */
  firstFieldError(): string | null {
    if (!this.details) return null;
    const entry = Object.values(this.details)[0];
    if (!entry) return null;
    return Array.isArray(entry) ? entry[0] : String(entry);
  }
}

function normalizeError(error: AxiosError): ApiError {
  const payload = error.response?.data as ErrorEnvelope | undefined;
  if (payload?.error) {
    return new ApiError(
      error.response!.status,
      payload.error.code,
      payload.error.message,
      (payload.error.details ?? null) as ApiErrorDetails | null,
    );
  }
  // Network failure / no response.
  return new ApiError(
    error.response?.status ?? 0,
    error.response?.status ?? 0,
    error.response ? error.message : "Network error — is the backend running?",
    null,
  );
}

export const api = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const access = tokenStore.access;
  if (access) config.headers.Authorization = `Bearer ${access}`;
  return config;
});

/* --- single-flight refresh ------------------------------------------------
 * When a 401 arrives, one refresh request runs; all other 401s wait on the
 * same promise and are replayed with the fresh token. A failed refresh
 * clears the session for everyone waiting.
 */
let refreshInFlight: Promise<boolean> | null = null;

async function doRefresh(): Promise<boolean> {
  const refresh = tokenStore.refresh;
  if (!refresh) return false;
  try {
    // Raw axios (no interceptors) to avoid recursion.
    const { data } = await axios.post<RefreshResponse>(
      `${BASE_URL}/api/v1/auth/token/refresh/`,
      { refresh },
      { headers: { "Content-Type": "application/json" } },
    );
    tokenStore.set(data.access, data.refresh); // rotation: store BOTH
    return true;
  } catch {
    return false;
  }
}

function clearSessionOnAuthFailure() {
  tokenStore.clear();
  window.dispatchEvent(new Event("cg:session-expired"));
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as (AxiosRequestConfig & { _retried?: boolean }) | undefined;
    const status = error.response?.status;

    if (status === 401 && original && !original._retried && tokenStore.refresh) {
      original._retried = true;
      if (!refreshInFlight) {
        refreshInFlight = doRefresh().finally(() => {
          refreshInFlight = null;
        });
      }
      const ok = await refreshInFlight;
      if (ok) {
        original.headers = { ...original.headers, Authorization: `Bearer ${tokenStore.access}` };
        return api.request(original);
      }
      clearSessionOnAuthFailure();
    } else if (status === 401 && original?._retried) {
      // Refreshed token was also rejected — stop the loop.
      clearSessionOnAuthFailure();
    }

    throw normalizeError(error);
  },
);

/** GET that unwraps DRF pagination when present, returning {items, count}. */
export async function getPaginated<T>(url: string, params?: Record<string, unknown>) {
  const { data } = await api.get<{ count: number; next: string | null; results?: T[] } | T[]>(url, { params });
  if (Array.isArray(data)) return { items: data, count: data.length };
  return { items: data.results ?? [], count: data.count };
}
