export interface GeneratedJD {
  title: string;
  summary?: string;
  responsibilities?: string[];
  requirements?: string[];
  nice_to_have?: string[];
  soft_skills?: string[];
  compensation?: string;
  about_company?: string;
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
  pdf_url: string | null;
  created_by: number | null;
  created_by_name?: string | null;
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
  page: number;
  per_page: number;
}

export interface JDCreate {
  title: string;
  content?: string | null;
  ownership?: "personal" | "public";
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
  pdf_url?: string | null;
  context?: string | null;
  skills?: string[];
  resume_skills?: string[];
  metadata?: Record<string, unknown>;
}

export interface JDTemplate {
  id: string;
  name: string;
  description?: string | null;
  file_url?: string | null;
  definition_json?: Record<string, unknown> | null;
  template_html?: string | null;
  template_css?: string | null;
  mapped_fields?: string[];
  version?: number;
  prompt?: string | null;
  is_custom: boolean;
  created_at?: string;
}

export interface ZohoJobOpening {
  id: string;
  Posting_Title?: string | null;
  Client_Name?: string | null;
  Job_Description?: string | null;
  Required_Skill_Set?: string | null;
  Work_Experience?: string | null;
  Job_Type?: string | null;
  Remote_Job?: boolean | null;
  City?: string | null;
  State?: string | null;
  Country?: string | null;
  No_of_Positions?: number | null;
  Job_Opening_Status?: string | null;
  Date_Opened?: string | null;
  Target_Date?: string | null;
  Salary?: number | string | null;
  Created_Time?: string | null;
  [key: string]: unknown;
}

export interface ZohoJobOpeningsResponse {
  data: ZohoJobOpening[];
  info?: {
    per_page?: number;
    count?: number;
    page?: number;
    more_records?: boolean;
  };
}
