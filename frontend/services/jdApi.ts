import type { GeneratedJD, JD, JDCreate, JDListResponse, JDPublishRequest, JDTemplate, ZohoJobOpeningsResponse } from "@/types/jd";

const BASE = process.env.NEXT_PUBLIC_BACKEND_URL ?? "";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  const stored = window.localStorage.getItem("recruitninja-auth");
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

export type CandidateRejection = {
  id: number;
  zoho_candidate_id: string;
  candidate_name: string;
  jd_id: number;
  jd_title: string;
  job_opening_id: string | null;
  recruiter_id: number;
  recruiter_name: string;
  reason: string;
  rejected_at: string;
};

export const jdApi = {
  list: (page?: number, perPage?: number): Promise<JDListResponse> => {
    const params = new URLSearchParams();
    if (page) params.set("page", String(page));
    if (perPage) params.set("per_page", String(perPage));
    const query = params.toString();
    return req(`/api/v1/jds${query ? `?${query}` : ""}`);
  },
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
  zohoJobOpenings: (page = 1, perPage = 200): Promise<ZohoJobOpeningsResponse> =>
    req(`/api/v1/jds/zoho/job-openings?page=${page}&per_page=${perPage}`),
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
  preview: (payload: JDPublishRequest): Promise<{ pdf_url: string }> =>
    req("/api/v1/jds/preview", { method: "POST", body: JSON.stringify(payload) }),
  listTemplates: (): Promise<{ items: JDTemplate[] }> => req("/api/v1/jds/templates"),
  getTemplate: (templateId: string): Promise<JDTemplate> =>
    req(`/api/v1/jds/templates/${encodeURIComponent(templateId)}`),
  uploadTemplate: (name: string, file: File, description?: string): Promise<JDTemplate> => {
    const form = new FormData();
    form.append("name", name);
    if (description) form.append("description", description);
    form.append("file", file);
    return req("/api/v1/jds/templates/upload", { method: "POST", body: form });
  },
  updateTemplate: (templateId: string, payload: { name?: string; description?: string | null; definition_json?: Record<string, unknown> }): Promise<JDTemplate> =>
    req(`/api/v1/jds/templates/${encodeURIComponent(templateId)}`, { method: "PUT", body: JSON.stringify(payload) }),
  previewTemplate: (templateId: string): Promise<{ pdf_url: string }> =>
    req(`/api/v1/jds/templates/${encodeURIComponent(templateId)}/preview`, { method: "POST" }),
  deleteTemplate: (templateId: string): Promise<void> => {
    return req(`/api/v1/jds/templates/${encodeURIComponent(templateId)}`, { method: "DELETE" });
  },
  sourceCandidates: (jdId: number, page = 1, perPage = 100, filters?: {
    skills?: string[];
    location?: string;
    seniority?: string;
    allCandidates?: boolean;
    noticePeriod?: string;
    currentCompany?: string;
    education?: string;
    employmentType?: string;
    visaStatus?: string;
    availability?: string;
    relocationPreference?: string;
    recency?: string;
    goodSkills?: string[];
  }): Promise<{
    jd_id: number;
    jd_title: string;
    search_skills: string[];
    required_skills: string[];
    good_to_have_skills?: string[];
    search_location?: string | null;
    search_seniority?: string | null;
    search_strategy?: string | null;
    search_notice?: string | null;
    zoho_criteria?: string | null;
    pipeline_counts?: {
      retrieved_from_zoho: number;
      deterministic_filtered: number;
      sent_to_scoring: number;
      sent_to_llm: number;
      returned: number;
    };
    filter_rejections?: Record<string, number>;
    experience_requirement: string | null;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    candidates: any[];
    total: number;
  }> => {
    const params = new URLSearchParams({
      jd_id: String(jdId),
      page: String(page),
      per_page: String(perPage),
    });
    if (filters?.skills?.length) params.set("skills", filters.skills.join(","));
    if (filters?.location) params.set("location", filters.location);
    if (filters?.seniority) params.set("seniority", filters.seniority);
    if (filters?.allCandidates) params.set("all_candidates", "true");
    if (filters?.noticePeriod) params.set("notice_period", filters.noticePeriod);
    if (filters?.currentCompany) params.set("current_company", filters.currentCompany);
    if (filters?.education) params.set("education", filters.education);
    if (filters?.employmentType) params.set("employment_type", filters.employmentType);
    if (filters?.visaStatus) params.set("visa_status", filters.visaStatus);
    if (filters?.availability) params.set("availability", filters.availability);
    if (filters?.relocationPreference) params.set("relocation_preference", filters.relocationPreference);
    if (filters?.recency) params.set("recency", filters.recency);
    if (filters?.goodSkills?.length) params.set("good_skills", filters.goodSkills.join(","));
    return req(`/api/v1/sourcing/candidates?${params.toString()}`);
  },
  rejectCandidate: (payload: {
    jd_id: number;
    zoho_candidate_id: string;
    candidate_name: string;
    job_opening_id?: string | null;
    reason: string;
  }): Promise<{ status: string }> =>
    req("/api/v1/sourcing/candidate-rejections", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listCandidateRejections: (filters?: { jdId?: number; recruiterId?: number }): Promise<CandidateRejection[]> => {
    const params = new URLSearchParams();
    if (filters?.jdId) params.set("jd_id", String(filters.jdId));
    if (filters?.recruiterId) params.set("recruiter_id", String(filters.recruiterId));
    const query = params.toString();
    return req(`/api/v1/sourcing/candidate-rejections${query ? `?${query}` : ""}`);
  },
  restoreCandidateRejection: (rejectionId: number): Promise<void> =>
    req(`/api/v1/sourcing/candidate-rejections/${rejectionId}`, { method: "DELETE" }),
  delete: (id: number): Promise<void> => req(`/api/v1/jds/${id}`, { method: "DELETE" }),
};
