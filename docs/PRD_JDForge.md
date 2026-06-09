# Product Requirements Document (PRD)
## JDForge — AI-Powered Hiring Platform

| Field | Value |
|---|---|
| **Product Name** | JDForge |
| **Version** | 0.2.0 (Beta) |
| **Document Version** | 1.0 |
| **Date** | June 2026 |
| **Status** | Draft |
| **Owner** | Product Team |

---

## 1. Executive Summary

JDForge is an AI-powered internal hiring platform designed to streamline how organizations **create, manage, and track Job Descriptions (JDs)**. The platform centralizes JD storage, enables AI-assisted generation of new JDs, and provides a clean dashboard for HR teams and hiring managers to work from a single source of truth.

The product is currently in **beta (v0.2.0)**, with core CRUD and file-management capabilities working. The AI generation feature is planned for the next sprint.

---

## 2. Problem Statement

| Pain Point | Impact |
|---|---|
| JDs scattered across email threads, shared drives, and local desktops | Hiring managers can't find the right template; duplicate efforts |
| Inconsistent JD formats across departments | Poor candidate experience; compliance risk |
| No centralized audit trail for JD versions and approvals | Legal and governance gap |
| Manual JD writing is time-consuming | Time-to-hire increases by days |

---

## 3. Goals & Success Metrics

### Business Goals
- Reduce average JD creation time from **~3 hours → <30 minutes** with AI assistance
- Provide a **single source of truth** for all JDs across the organization
- Enable **searchable, filterable** JD library accessible by all stakeholders

### Key Performance Indicators (KPIs)

| Metric | Target (6-month) |
|---|---|
| JDs created via platform | ≥ 80% of all new hires |
| Average JD generation time | < 30 minutes |
| Platform adoption (DAU/MAU) | ≥ 60% |
| JD search query success rate | ≥ 85% |
| API uptime | 99.9% |

---

## 4. User Personas

### Persona 1 — HR Manager (Primary User)
- **Goal**: Upload, search, and share JDs across the hiring team
- **Pain Point**: Spends hours reformatting old JDs for new roles
- **Key Workflows**: Search JDs, upload new PDFs, review AI suggestions

### Persona 2 — Hiring Manager / Department Head
- **Goal**: Get a ready-to-post JD for a new opening quickly
- **Pain Point**: Relies on HR to draft, causing delays
- **Key Workflows**: Request JD generation, review output, approve for posting

### Persona 3 — Recruiter
- **Goal**: Access the latest, approved JD for a role to post externally
- **Pain Point**: Uses outdated JDs due to unclear version history
- **Key Workflows**: View JDs, download PDFs, filter by department/seniority

### Persona 4 — Admin / System Owner
- **Goal**: Manage user roles, storage, and system health
- **Pain Point**: No tooling to audit JD changes or storage usage
- **Key Workflows**: Monitor health, manage users, configure storage

---

## 5. Feature Requirements

### 5.1 Core (Current — v0.2.0 BETA) ✅

#### F1 — JD Repository / Dashboard
- **F1.1**: Display all JDs in a sortable, filterable table (sorted by creation date desc)
- **F1.2**: Show JD ID, name, file link, and creation date per row
- **F1.3**: Client-side search/filter by JD name
- **F1.4**: Statistics bar: Total JDs, JDs this month, search results count
- **F1.5**: Sticky top navigation with branding

#### F2 — JD File Management
- **F2.1**: Upload JD as PDF (stored locally in `/uploads/` directory)
- **F2.2**: Serve uploaded PDFs via static file serving at `/uploads/<filename>`
- **F2.3**: Link to open PDF in new browser tab from the JD table row
- **F2.4**: Delete a JD record (soft delete via API, removes DB record)

#### F3 — REST API
- **F3.1**: `GET /api/v1/jds` — list all JDs with pagination envelope
- **F3.2**: `GET /api/v1/jds/{id}` — fetch single JD by ID
- **F3.3**: `POST /api/v1/jds` — create a new JD record
- **F3.4**: `DELETE /api/v1/jds/{id}` — delete a JD record
- **F3.5**: `GET /health` — health check endpoint

#### F4 — Data Persistence
- **F4.1**: Store JD metadata (name, file_url, timestamps) in PostgreSQL
- **F4.2**: Audit timestamps (`created_at`, `updated_at`) on every record
- **F4.3**: Database session management with connection pooling

---

### 5.2 Planned (Next Phase — v0.3.0)

#### F5 — AI JD Generation (Anthropic Claude)
- **F5.1**: Input form: Role title, department, seniority level, key responsibilities
- **F5.2**: Generate structured JD using Claude AI via Anthropic API
- **F5.3**: Editable preview before saving
- **F5.4**: Save generated JD as PDF or rich text
- **F5.5**: Regenerate/refine with feedback loop

#### F6 — Authentication & Authorization
- **F6.1**: User login (email/password or SSO)
- **F6.2**: Role-based access control (Admin, HR Manager, Hiring Manager, Recruiter)
- **F6.3**: JWT-based session management

#### F7 — S3 Storage
- **F7.1**: Migrate file storage from local disk to AWS S3
- **F7.2**: Signed URL generation for secure, time-limited file access
- **F7.3**: Retain backward compatibility with locally-stored files

#### F8 — Advanced JD Management
- **F8.1**: JD version history and change tracking
- **F8.2**: JD status workflow: Draft → Review → Approved → Published
- **F8.3**: Tagging by department, role-level, technology stack
- **F8.4**: Pagination support in list API

---

### 5.3 Future (v1.0+)

| Feature | Description |
|---|---|
| **F9 — Candidate Matching** | Match uploaded resumes against JDs using AI |
| **F10 — Analytics Dashboard** | JD performance metrics (views, applications, time-to-fill) |
| **F11 — ATS Integration** | Push JDs directly to external ATS (Greenhouse, Lever, Workday) |
| **F12 — Multi-tenant** | Support for multiple organizations / business units |
| **F13 — Notifications** | Email/Slack alerts for JD approvals and expirations |

---

## 6. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Performance** | API response time < 200ms for list endpoints (P95) |
| **Availability** | 99.9% uptime SLA for production |
| **Security** | HTTPS only; CORS restricted to known origins; secrets in env vars |
| **Scalability** | Stateless backend; horizontal scaling via container replicas |
| **Accessibility** | WCAG 2.1 AA compliance for frontend UI |
| **Browser Support** | Chrome, Firefox, Safari, Edge (latest 2 versions) |
| **Data Retention** | JD records retained for minimum 7 years for compliance |
| **Audit Logging** | All create/update/delete actions logged with user + timestamp |

---

## 7. Constraints & Assumptions

- **Anthropic API key** is required for AI generation features
- File storage is **local disk in development**; S3 in production
- PostgreSQL is the only supported database
- The system targets **internal enterprise use** — not a public-facing product
- Initial deployment targets are **Vercel** (frontend) and a managed cloud service (backend)

---

## 8. Out of Scope (v0.2.0)

- Resume parsing and candidate management
- External job board posting integration
- Mobile native applications
- Real-time collaboration on JD editing
- Billing / subscription management

---

## 9. Product Roadmap

```
Phase 1 (NOW)     — Core CRUD + File Management (v0.2.0) ✅
Phase 2 (Q3 2026) — AI JD Generation + Auth + S3 (v0.3.0)
Phase 3 (Q4 2026) — Status workflows + Analytics (v0.4.0)
Phase 4 (Q1 2027) — Candidate matching + ATS Integration (v1.0)
```

---

## 10. Open Questions

1. Should deleted JDs be soft-deleted (hidden) or hard-deleted from DB?
2. Who are the approvers in the JD review workflow — only HR or also department heads?
3. Is there a maximum file size for uploaded JDs? (Recommended: 10MB limit)
4. Should AI-generated JDs be stored as structured data (JSON/markdown) or directly as PDFs?
5. What are the compliance / data residency requirements for JD storage?
