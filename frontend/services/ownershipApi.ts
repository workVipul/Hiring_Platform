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
      "Content-Type": "application/json",
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

export type SLARule = {
  id: number;
  blueprint: string;
  stage_name: string;
  duration_days: number;
  active: boolean;
};

export type CandidateOwnership = {
  id: number;
  zoho_candidate_id: string;
  candidate_name: string;
  job_opening_id: string | null;
  owner_recruiter_id: number | null;
  owner_recruiter_name: string;
  sla_stage_id: number;
  sla_stage_name: string | null;
  locked_at: string;
  expires_at: string;
  status: string;
  remaining_seconds: number;
  is_locked_by_other: boolean;
};

export type RecruiterOption = {
  id: number;
  name: string;
  email: string;
};

export type OwnershipHistory = {
  id: number;
  candidate_id: string;
  action: string;
  old_owner: string | null;
  new_owner: string | null;
  old_stage: string | null;
  new_stage: string | null;
  performed_by: string;
  timestamp: string;
};

export const ownershipApi = {
  listSlaRules: (activeOnly = false): Promise<SLARule[]> =>
    req(`/api/v1/ownership/sla-rules${activeOnly ? "?active_only=true" : ""}`),
  createSlaRule: (payload: { blueprint: string; stage_name: string; duration_days: number; active: boolean }): Promise<SLARule> =>
    req("/api/v1/ownership/sla-rules", { method: "POST", body: JSON.stringify(payload) }),
  updateSlaRule: (id: number, payload: Partial<{ blueprint: string; stage_name: string; duration_days: number; active: boolean }>): Promise<SLARule> =>
    req(`/api/v1/ownership/sla-rules/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  listRecruiters: (): Promise<RecruiterOption[]> => req("/api/v1/ownership/recruiters"),
  listActiveOwnerships: (): Promise<CandidateOwnership[]> => req("/api/v1/ownership/active"),
  listMyOwnerships: (): Promise<CandidateOwnership[]> => req("/api/v1/ownership/mine"),
  accept: (payload: {
    zoho_candidate_id: string;
    candidate_name: string;
    job_opening_id?: string | null;
    sla_stage_id: number;
  }): Promise<CandidateOwnership> =>
    req("/api/v1/ownership/accept", { method: "POST", body: JSON.stringify(payload) }),
  changeStage: (zohoCandidateId: string, slaStageId: number): Promise<CandidateOwnership> =>
    req(`/api/v1/ownership/${encodeURIComponent(zohoCandidateId)}/stage`, {
      method: "PATCH",
      body: JSON.stringify({ sla_stage_id: slaStageId }),
    }),
  release: (zohoCandidateId: string): Promise<CandidateOwnership> =>
    req(`/api/v1/ownership/${encodeURIComponent(zohoCandidateId)}/release`, { method: "POST" }),
  reassign: (zohoCandidateId: string, newOwnerRecruiterId: number): Promise<CandidateOwnership> =>
    req(`/api/v1/ownership/${encodeURIComponent(zohoCandidateId)}/reassign`, {
      method: "POST",
      body: JSON.stringify({ new_owner_recruiter_id: newOwnerRecruiterId }),
    }),
  history: (zohoCandidateId: string): Promise<OwnershipHistory[]> =>
    req(`/api/v1/ownership/${encodeURIComponent(zohoCandidateId)}/history`),
};
