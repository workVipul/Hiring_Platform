// Mirrors backend app/schemas/jd.py — keep these in sync.

export interface JD {
  id: number;
  name: string;
  file_url: string;     // local path like "uploads/file.pdf" or future S3 URL
  created_at: string;   // ISO 8601 datetime string
  updated_at: string;
}

export interface JDListResponse {
  items: JD[];
  total: number;
}

export interface JDCreate {
  name: string;
  file_url: string;
}
