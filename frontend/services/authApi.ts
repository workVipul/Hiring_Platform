import type { LoginResponse } from "@/types/user";

const BASE = process.env.NEXT_PUBLIC_BACKEND_URL ?? "";

async function req<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(opts?.headers ?? {}) },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

export const authApi = {
  login: (email: string, password: string): Promise<LoginResponse> =>
    req("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  register: (name: string, email: string, password: string): Promise<{ id: number; name: string; email: string }> =>
    req("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ name, email, password }),
    }),
};
