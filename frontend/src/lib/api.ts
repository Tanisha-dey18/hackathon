const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "";
const TOKEN_KEY = "sentinel_token";

export function getToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable */
  }
}

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(formatDetail(detail) || `Request failed (${status})`);
    this.status = status;
    this.detail = detail;
  }
}

function formatDetail(detail: unknown): string {
  if (!detail) return "";
  if (typeof detail === "string") return detail;
  if (typeof detail === "object") {
    const d = detail as Record<string, unknown>;
    if (d.message) return [d.message, d.issue, d.debug_id && `debug_id ${d.debug_id}`].filter(Boolean).join(" · ");
    if (Array.isArray(d.errors)) return (d.errors as { msg: string; loc: string[] }[]).map((e) => `${e.loc.slice(-1)}: ${e.msg}`).join("; ");
  }
  return JSON.stringify(detail);
}

export async function api<T = any>(path: string, opts: RequestInit & { json?: unknown } = {}): Promise<T> {
  const headers = new Headers(opts.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let body = opts.body;
  if (opts.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(opts.json);
  }
  const res = await fetch(`${BASE}${path}`, { ...opts, headers, body });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    if (res.status === 401 && token && !path.includes("/auth/login")) {
      setToken(null);
      window.dispatchEvent(new Event("sentinel:logout"));
    }
    throw new ApiError(res.status, data?.detail ?? data);
  }
  return data as T;
}

export function wsUrl(path: string): string {
  const token = getToken() ?? "";
  if (BASE) return `${BASE.replace(/^http/, "ws")}${path}?token=${encodeURIComponent(token)}`;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}${path}?token=${encodeURIComponent(token)}`;
}

export const apiBase = BASE;
