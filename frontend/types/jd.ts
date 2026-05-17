export interface GeneratedJD {
  title: string;
  summary?: string;
  responsibilities?: string[];
  requirements?: string[];
  nice_to_have?: string[];
  compensation?: string;
  about_company?: string;
  jd_score?: number | null;
  skills?: string[];
  resume_skills?: string[];
  metadata?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface JD {
  id: number;
  title: string;
  content: string | null;
  ownership: "personal" | "public";
  jd_score: number | null;
  pdf_url: string | null;
  created_by: number | null;
  context: string | null;
  skills: string[];
  resume_skills: string[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface JDListResponse {
  items: JD[];
  total: number;
}

export interface JDCreate {
  title: string;
  content?: string | null;
  ownership?: "personal" | "public";
  jd_score?: number | null;
  pdf_url?: string | null;
  context?: string | null;
  skills?: string[];
  resume_skills?: string[];
  metadata?: Record<string, unknown>;
}

export interface JDPublishRequest {
  title: string;
  content: string;
  ownership: "personal" | "public";
  jd_score?: number | null;
  pdf_url?: string | null;
  context?: string | null;
  skills?: string[];
  resume_skills?: string[];
  metadata?: Record<string, unknown>;
}
