import type { JD, JDCreate, JDListResponse } from "@/types/jd";

// In dev: NEXT_PUBLIC_BACKEND_URL is undefined, so we use the Next.js proxy at /api/v1.
// In production (Vercel): set NEXT_PUBLIC_BACKEND_URL=https://your-backend.vercel.app
// This pattern is already used in the existing repo — we're following the same convention.
const BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail ?? `Request failed: ${res.status}`);
  }

  // 204 No Content has no body
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ---- JD endpoints ----

export const jdApi = {
  /** Fetch all JDs, newest first. */
  list: (): Promise<JDListResponse> =>
    request<JDListResponse>("/api/v1/jds"),

  /** Fetch a single JD by id. */
  get: (id: number): Promise<JD> =>
    request<JD>(`/api/v1/jds/${id}`),

  /** Create a JD record (called after upload or AI generation). */
  create: (payload: JDCreate): Promise<JD> =>
    request<JD>("/api/v1/jds", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  /** Delete a JD record. */
  delete: (id: number): Promise<void> =>
    request<void>(`/api/v1/jds/${id}`, { method: "DELETE" }),
};
