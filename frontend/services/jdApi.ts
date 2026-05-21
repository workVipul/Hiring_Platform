import type { GeneratedJD, JD, JDCreate, JDListResponse, JDPublishRequest } from "@/types/jd";

const BASE = process.env.NEXT_PUBLIC_BACKEND_URL ?? "";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  const stored = window.localStorage.getItem("ninjaforge-auth");
  if (!stored) return null;
  try {
    const parsed = JSON.parse(stored);
    return parsed?.state?.token ?? null;
  } catch {
    return null;
  }
}

async function req<T>(path: string, opts?: RequestInit): Promise<T> {
  const token = getToken();
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: {
      ...(opts?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(opts?.headers ?? {}),
    },
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
  upload: (file: File): Promise<JD> => {
    const form = new FormData();
    form.append("file", file);
    return req("/api/v1/jds/upload", { method: "POST", body: form });
  },
  create: (payload: JDCreate): Promise<JD> =>
    req("/api/v1/jds", { method: "POST", body: JSON.stringify(payload) }),
  update: (id: number, payload: JDCreate): Promise<JD> =>
    req(`/api/v1/jds/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  generate: (raw_input: string, input_type = "text"): Promise<GeneratedJD> =>
    req("/api/v1/jds/generate", {
      method: "POST",
      body: JSON.stringify({ raw_input, input_type }),
    }),
  transcribe: (file: File): Promise<{ text: string }> => {
    const form = new FormData();
    form.append("file", file);
    return req("/api/v1/jds/transcribe", { method: "POST", body: form });
  },
  refine: (id: number, instruction: string, content?: string): Promise<GeneratedJD> =>
    req(`/api/v1/jds/${id}/refine`, {
      method: "POST",
      body: JSON.stringify({ instruction, content }),
    }),
  publish: (id: number, payload: JDPublishRequest): Promise<JD> =>
    req(`/api/v1/jds/${id}/publish`, { method: "POST", body: JSON.stringify(payload) }),
  sourceCandidates: (jdId: number, page = 1, perPage = 20): Promise<{
    jd_id: number;
    jd_title: string;
    search_skills: string[];
    candidates: any[];
    total: number;
  }> => req("/api/v1/sourcing/candidates", {
    method: "POST",
    body: JSON.stringify({ jd_id: jdId, page, per_page: perPage }),
  }),
  delete: (id: number): Promise<void> => req(`/api/v1/jds/${id}`, { method: "DELETE" }),
};
