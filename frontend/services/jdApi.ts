import type { JD, JDListResponse } from "@/types/jd";

const BASE = process.env.NEXT_PUBLIC_BACKEND_URL ?? "";

async function req<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const jdApi = {
  list: (): Promise<JDListResponse> => req("/api/v1/jds"),
  get: (id: number): Promise<JD> => req(`/api/v1/jds/${id}`),
  delete: (id: number): Promise<void> => req(`/api/v1/jds/${id}`, { method: "DELETE" }),
};