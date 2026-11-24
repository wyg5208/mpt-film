// fetch wrapper: base URL, Bearer injection, {status,message,data} envelope unwrap,
// single 401 -> refresh retry. Master key never persisted; token lives in memory +
// sessionStorage (migration 4.B front-end session flow).
import {
  getToken,
  setToken,
  clearToken,
  getMasterKeyOnce,
} from "../app/session";

import { apiBase } from "./env";

const API_BASE = apiBase();
export const V1 = `${API_BASE}/api/v1`;

export class ApiError extends Error {
  code?: string;
  status: number;
  constructor(status: number, message: string, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function refresh(): Promise<boolean> {
  // Refresh needs a still-valid credential; x-api-key path is not used here.
  const token = getToken();
  if (!token) return false;
  const res = await fetch(`${V1}/auth/refresh`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return false;
  const body = await res.json();
  const data = body?.data;
  if (data?.access_token) {
    setToken(data.access_token, data.expires_at);
    return true;
  }
  return false;
}

export async function request<T = any>(
  path: string,
  init: RequestInit = {},
  allowRetry = true
): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type"))
    headers.set("Content-Type", "application/json");

  const res = await fetch(`${V1}${path}`, { ...init, headers });

  if (res.status === 401 && allowRetry) {
    if (await refresh()) {
      return request<T>(path, init, false);
    }
    clearToken();
    throw new ApiError(401, "unauthorized", "token_expired");
  }

  let body: any = null;
  const text = await res.text();
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    /* non-JSON (e.g. SSE handled elsewhere) */
  }

  if (!res.ok) {
    const code = body?.data?.code;
    throw new ApiError(res.status, body?.message || res.statusText, code);
  }
  // Envelope: {status, message, data}. Return the inner data when present.
  if (body && typeof body === "object" && "status" in body) {
    if (body.status !== 200) {
      throw new ApiError(body.status, body.message, body.data?.code);
    }
    return body.data as T;
  }
  return body as T;
}

export const api = {
  get: <T = any>(path: string) => request<T>(path),
  post: <T = any>(path: string, data?: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(data ?? {}) }),
  // Multipart upload: fetch sets the boundary itself, so the raw FormData is
  // passed through without the JSON Content-Type that `post` would apply.
  postForm: <T = any>(path: string, form: FormData) =>
    request<T>(path, { method: "POST", body: form }),
  put: <T = any>(path: string, data?: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(data ?? {}) }),
  patch: <T = any>(path: string, data?: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(data ?? {}) }),
  del: <T = any>(path: string) => request<T>(path, { method: "DELETE" }),
};

// orval mutator adapter: generated TanStack Query hooks (src/api/generated/)
// call this with an axios-style config object; we translate onto the shared
// `request` so Bearer injection / envelope unwrap / 401 refresh stay in one
// place. Generated urls carry the /api/v1 prefix, which `request`
// re-prepends, so strip it here.
export async function orvalRequest<T = any>(
  config: {
    url: string;
    method?: string;
    data?: unknown;
    params?: Record<string, unknown>;
    headers?: Record<string, string>;
    signal?: AbortSignal;
  },
  extra?: RequestInit
): Promise<T> {
  const { url, method = "GET", data, params, headers, signal } = config;
  let path = url.startsWith("/api/v1") ? url.slice("/api/v1".length) || "/" : url;
  if (params) {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(params))
      if (v !== undefined && v !== null) q.append(k, String(v));
    const s = q.toString();
    if (s) path += (path.includes("?") ? "&" : "?") + s;
  }
  // fetch sets the multipart boundary itself; a hand-written Content-Type for
  // FormData bodies would break the request, so drop it in that case.
  const hdrs: Record<string, string> = { ...(extra?.headers as Record<string, string>), ...(headers ?? {}) };
  if (data instanceof FormData) delete hdrs["Content-Type"];
  const init: RequestInit = { ...extra, method, signal, headers: hdrs };
  if (data !== undefined && method !== "GET" && method !== "HEAD")
    init.body =
      typeof data === "string" || data instanceof FormData ? data : JSON.stringify(data);
  return request<T>(path, init);
}

// Login uses the master key exactly once; it must not go through the bearer path.
export async function login(apiKey: string) {
  const res = await fetch(`${V1}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey }),
  });
  const body = await res.json();
  if (!res.ok || body?.status !== 200) {
    throw new ApiError(res.status, body?.message, body?.data?.code);
  }
  const data = body.data;
  setToken(data.access_token, data.expires_at);
  return data;
}

export { getMasterKeyOnce };
