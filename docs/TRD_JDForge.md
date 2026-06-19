# Technical Requirements Document (TRD)
## JDForge — AI-Powered Hiring Platform

| Field | Value |
|---|---|
| **Product** | JDForge |
| **Backend Version** | 0.2.0 |
| **Document Version** | 1.0 |
| **Date** | June 2026 |
| **Tech Lead** | Engineering Team |

---

## 1. System Architecture Overview

JDForge follows a **decoupled, two-tier web application architecture** with a REST API backend and a separate frontend SPA.

```
┌─────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                          │
│                                                             │
│   Next.js 16 (React 19)   ──  Vercel (CDN + SSR)           │
│   TypeScript, Tailwind CSS                                  │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTPS REST API calls
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                        API LAYER                             │
│                                                             │
│   FastAPI (Python 3.11+)                                    │
│   Uvicorn ASGI server                                       │
│   Pydantic v2 validation                                    │
│   SQLAlchemy 2.0 ORM                                        │
└────────────────────────┬────────────────────────────────────┘
                         │ SQLAlchemy sessions
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      DATA LAYER                              │
│                                                             │
│   PostgreSQL 15+  (primary datastore)                       │
│   Local disk /uploads/  →  [future] AWS S3                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Technology Stack

### 2.1 Backend

| Component | Technology | Version |
|---|---|---|
| **Language** | Python | 3.11+ |
| **Web Framework** | FastAPI | Latest |
| **ASGI Server** | Uvicorn (standard) | Latest |
| **ORM** | SQLAlchemy | ≥ 2.0 |
| **Database** | PostgreSQL | 15+ |
| **DB Driver** | psycopg2-binary | Latest |
| **Settings** | pydantic-settings | Latest |
| **AI Integration** | Anthropic Claude SDK | Latest |
| **Caching** | cachetools | Latest |

### 2.2 Frontend

| Component | Technology | Version |
|---|---|---|
| **Framework** | Next.js | 16.2.5 |
| **Language** | TypeScript | 5.x |
| **UI Library** | React | 19.2.4 |
| **Styling** | Tailwind CSS v4 + Custom CSS Variables | ^4 |
| **HTTP Client** | Native Fetch API | — |
| **Fonts** | Syne, DM Mono (Google Fonts) | — |
| **Package Manager** | npm | — |

### 2.3 Infrastructure (Current Dev / Target Prod)

| Resource | Development | Production |
|---|---|---|
| **Frontend Hosting** | `npm run dev` (localhost:3000) | Vercel |
| **Backend Hosting** | Uvicorn (localhost:8000) | Railway / Render / AWS ECS |
| **Database** | PostgreSQL localhost | Supabase / AWS RDS / Neon |
| **File Storage** | Local `/uploads/` directory | AWS S3 |
| **Environment Config** | `.env` file | Platform env vars |

---

## 3. Data Models

### 3.1 Database Schema

#### Table: `jd`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `INTEGER` | PK, auto-increment, indexed | Unique identifier |
| `name` | `VARCHAR` | NOT NULL | Human-readable JD title |
| `file_url` | `VARCHAR` | NOT NULL | Local path (`uploads/file.pdf`) or future S3 key |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, server_default=now() | Record creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, server_default=now(), onupdate=now() | Last modification timestamp |

**Index**: `id` (primary key, B-tree)

#### Future Columns (v0.3.0+)

| Column | Type | Description |
|---|---|---|
| `role` | `VARCHAR` | Job role/title |
| `department` | `VARCHAR` | Department (Engineering, Product, Design…) |
| `seniority` | `VARCHAR` | Junior / Mid / Senior / Lead |
| `status` | `ENUM` | Draft / Review / Approved / Published |
| `generated_content` | `TEXT` | Full AI-generated JD body |
| `storage_backend` | `VARCHAR` | `local` or `s3` |
| `created_by` | `INTEGER` | FK → users.id |

---

### 3.2 Pydantic Schemas

#### Request: `JDCreate`
```python
class JDCreate(BaseModel):
    name: str
    file_url: str
```

#### Response: `JDResponse`
```python
class JDResponse(BaseModel):
    id: int
    name: str
    file_url: str
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
```

#### Response: `JDListResponse`
```python
class JDListResponse(BaseModel):
    items: list[JDResponse]
    total: int
```

---

### 3.3 TypeScript Types (Frontend Mirror)

```typescript
export interface JD {
  id: number;
  name: string;
  file_url: string;    // "uploads/file.pdf" or "https://s3.../file.pdf"
  created_at: string;  // ISO 8601
  updated_at: string;
}

export interface JDListResponse {
  items: JD[];
  total: number;
}
```

---

## 4. API Specification

**Base URL**: `http://localhost:8000` (dev) / `https://api.jdforge.com` (prod)  
**Prefix**: `/api/v1`  
**Content-Type**: `application/json`

### 4.1 Endpoints

#### `GET /api/v1/jds`
List all JDs, ordered by creation date descending.

**Response 200**:
```json
{
  "items": [
    {
      "id": 1,
      "name": "Senior Java Developer_5 to 8 years",
      "file_url": "uploads/Senior Java Developer_5 to 8 years.pdf",
      "created_at": "2026-06-01T10:00:00Z",
      "updated_at": "2026-06-01T10:00:00Z"
    }
  ],
  "total": 1
}
```

**Future query params**: `?skip=0&limit=20&status=draft&department=engineering`

---

#### `GET /api/v1/jds/{jd_id}`
Fetch a single JD by ID.

**Response 200**: Single `JDResponse` object  
**Response 404**: `{"detail": "JD not found"}`

---

#### `POST /api/v1/jds`
Create a new JD record (called after file upload or AI generation).

**Request Body**:
```json
{
  "name": "Backend Engineer - Senior",
  "file_url": "uploads/backend_engineer_senior.pdf"
}
```
**Response 201**: Created `JDResponse` object

---

#### `DELETE /api/v1/jds/{jd_id}`
Delete a JD record by ID.

**Response 204**: No content  
**Response 404**: `{"detail": "JD not found"}`

---

#### `GET /health`
Health check endpoint.

**Response 200**:
```json
{"status": "ok", "version": "0.2.0"}
```

---

## 5. Configuration & Environment Variables

### 5.1 Backend (`backend/.env`)

| Variable | Default | Required | Description |
|---|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:password@localhost:5432/jdforge` | ✅ | PostgreSQL connection string |
| `UPLOADS_DIR` | `uploads` | ✅ | Local directory for PDF storage |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | ✅ | Comma-separated CORS origins |
| `ANTHROPIC_API_KEY` | `""` | ⬜ (AI phase) | Anthropic Claude API key |

### 5.2 Frontend (`frontend/.env.local`)

| Variable | Default | Required | Description |
|---|---|---|---|
| `NEXT_PUBLIC_BACKEND_URL` | `""` (empty = same origin) | ✅ in prod | Backend API base URL |

---

## 6. CORS Policy

```python
origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",")]
app.add_middleware(CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

> **Production requirement**: Replace `["*"]` methods/headers with explicit allowlist. Add Vercel preview URLs to `ALLOWED_ORIGINS`.

---

## 7. File Storage Architecture

### Current (Development)
- Files stored in `backend/uploads/` directory
- Served via FastAPI `StaticFiles` at `/uploads/<filename>`
- URL format: `http://localhost:8000/uploads/file.pdf`

### Future (Production — S3)
- Upload directly to S3 bucket via pre-signed PUT URL
- Store S3 object key in `jd.file_url` column (e.g., `jds/2026/06/file.pdf`)
- Generate signed GET URLs for time-limited access
- **Zero frontend API changes required** — `resolveFileUrl()` in frontend handles both formats:
  ```typescript
  function resolveFileUrl(fileUrl: string): string {
    if (fileUrl.startsWith("http")) return fileUrl; // S3 full URL
    return `${BACKEND_URL}/${fileUrl}`;              // local path
  }
  ```

---

## 8. Database Session Management

```python
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- `pool_pre_ping=True` — validates connections before use; handles stale connections
- Sessions are per-request via FastAPI `Depends(get_db)`
- `autocommit=False` — explicit commits required

> **Production**: Configure `pool_size`, `max_overflow`, `pool_timeout` for load. Use PgBouncer for connection pooling at scale.

---

## 9. Security Requirements

| Area | Current State | Production Requirement |
|---|---|---|
| **Transport** | HTTP (dev only) | HTTPS everywhere (TLS 1.2+) |
| **Secrets** | `.env` file | Secrets manager (AWS Secrets Manager / Vault) |
| **CORS** | Configurable via env | Explicit origin allowlist only |
| **Auth** | None (open API) | JWT + RBAC (Phase 2) |
| **File Validation** | None | MIME type check, max file size (10MB), virus scan |
| **SQL Injection** | ORM (SQLAlchemy) — protected | No raw SQL; parameterized queries only |
| **Rate Limiting** | None | API rate limiting (e.g., 100 req/min per IP) |
| **Input Validation** | Pydantic schemas | Strict schema validation on all inputs |
| **Dependency Scanning** | None | Dependabot / Snyk in CI |

---

## 10. Database Migration Strategy

### Current
```python
# In main.py — runs on every startup
Base.metadata.create_all(bind=engine)
```
> ⚠️ **Acceptable in development only.** `create_all` does NOT alter existing tables.

### Production Requirement
- Adopt **Alembic** for versioned database migrations
- Migrations checked into source control
- Automatic migration on deploy (CI/CD step)

```bash
# Setup commands
pip install alembic
alembic init alembic
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

---

## 11. Frontend Architecture

### Routing (Next.js App Router)
| Route | Component | Description |
|---|---|---|
| `/` | `app/page.tsx` | Main JD dashboard with full-featured table |
| `/jds` | `app/jds/page.tsx` + `JDTable` | Alternative JD listing view |
| `/api/v1/[...path]` | Next.js API proxy | Proxy to backend (optional) |

### State Management
- **Local React state** (`useState`, `useMemo`) — sufficient for current scale
- No Redux/Zustand required yet; introduce when global state is needed (auth, user prefs)

### API Service Layer
```typescript
// services/jdApi.ts
export const jdApi = {
  list: (): Promise<JDListResponse> => req("/api/v1/jds"),
  get: (id: number): Promise<JD> => req(`/api/v1/jds/${id}`),
  delete: (id: number): Promise<void> => req(`/api/v1/jds/${id}`, { method: "DELETE" }),
};
```
> All API calls go through a centralized `req<T>()` function that handles error parsing and 204 responses.

---

## 12. Performance Requirements

| Metric | Target | Strategy |
|---|---|---|
| API list response | < 200ms (P95) | DB index on `created_at`, pagination |
| Frontend first contentful paint | < 1.5s | Next.js SSR / static generation |
| File upload time | < 5s for 10MB PDF | Streaming upload, S3 multipart |
| Concurrent users supported | 100+ simultaneous | Stateless API; horizontal scaling |

---

## 13. Monitoring & Observability

| Area | Tool (Recommended) | What to Monitor |
|---|---|---|
| **API Health** | Uptime Robot / Datadog | `/health` endpoint, response time |
| **Error Tracking** | Sentry | Backend exceptions, frontend JS errors |
| **Logging** | Python `logging` + structured JSON | All request/response logs, errors |
| **Database** | pg_stat_activity | Long-running queries, connection count |
| **Infrastructure** | AWS CloudWatch / Grafana | CPU, memory, disk usage |

---

## 14. CI/CD Pipeline (Recommended)

```
Push to main
    │
    ├─ Run linters (ESLint, ruff/flake8)
    ├─ Run type checks (tsc --noEmit, mypy)
    ├─ Run unit tests (pytest, jest)
    ├─ Run DB migration checks (alembic check)
    │
    ├─ [On PR] Deploy preview to Vercel
    │
    └─ [On merge to main]
        ├─ Deploy frontend → Vercel (auto)
        └─ Deploy backend → Railway/Render/ECS
            └─ Run alembic upgrade head
```

---

## 15. Production Readiness Checklist

### Must-Have Before Production

- [ ] **Authentication**: Implement JWT auth with role-based access control
- [ ] **HTTPS**: Enable TLS on all endpoints (backend + frontend)
- [ ] **Database Migrations**: Replace `create_all` with Alembic migrations
- [ ] **S3 Storage**: Move file uploads off local disk to S3
- [ ] **CORS Hardening**: Restrict to specific allowed origins only
- [ ] **File Validation**: MIME type, size limit, malware scan on upload
- [ ] **Rate Limiting**: Add rate limiting middleware (e.g., `slowapi`)
- [ ] **Error Logging**: Integrate Sentry for error tracking
- [ ] **Environment Variables**: All secrets in platform env vars, not `.env` files
- [ ] **Health Monitoring**: Alerting on `/health` endpoint failures
- [ ] **Pagination**: Implement `skip`/`limit` on `GET /api/v1/jds` for scale
- [ ] **Soft Deletes**: Consider `is_deleted` flag instead of hard-deletes
- [ ] **Input Sanitization**: Validate file names, strip path traversal characters

### Nice-to-Have

- [ ] **Audit Log Table**: Store all create/delete events with user + timestamp
- [ ] **API Documentation**: Auto-generated OpenAPI docs accessible at `/docs`
- [ ] **Load Testing**: Run k6/Locust before go-live
- [ ] **Backup Strategy**: Daily PostgreSQL dumps + S3 versioning
- [ ] **CDN**: Serve frontend assets from CDN edge nodes
