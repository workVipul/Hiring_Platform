# Production Readiness Runbook
## JDForge — AI-Powered Hiring Platform

| Field | Value |
|---|---|
| **Document Type** | Operations Runbook |
| **Version** | 1.0 |
| **Date** | June 2026 |

---

## 1. Pre-Production Checklist

Run through **every item** before flipping traffic to production.

### 1.1 Code Quality
- [ ] All linting passes: `cd frontend && npm run lint`
- [ ] TypeScript compiles clean: `npx tsc --noEmit`
- [ ] Backend type checks pass: `mypy app/`
- [ ] No hardcoded secrets in source code (grep for `password`, `api_key`, `secret`)

### 1.2 Database
- [ ] Alembic installed and initialized: `pip install alembic && alembic init alembic`
- [ ] Initial migration generated: `alembic revision --autogenerate -m "initial_jd_schema"`
- [ ] Migration tested against a clean DB: `alembic upgrade head`
- [ ] **Remove** `Base.metadata.create_all(bind=engine)` from `main.py`
- [ ] Database backups configured (daily automated dumps)

### 1.3 Security
- [ ] All secrets moved to platform environment variables (not `.env` in repo)
- [ ] HTTPS enabled on backend domain
- [ ] CORS origins restricted to production frontend URL only
- [ ] File upload validation added (MIME type + size limit)
- [ ] Rate limiting middleware added (`slowapi`)
- [ ] Auth middleware stubbed/implemented

### 1.4 Infrastructure
- [ ] Backend health check `/health` returns 200
- [ ] PostgreSQL connection tested from production backend
- [ ] S3 bucket created with correct IAM permissions
- [ ] Uploads directory migrated to S3

---

## 2. Environment Setup

### 2.1 Backend Production Environment Variables

```bash
# Database
DATABASE_URL=postgresql://jdforge_user:STRONG_PASS@your-rds-host:5432/jdforge_prod

# Storage
UPLOADS_DIR=uploads  # Keep for fallback; use S3 in production

# CORS
ALLOWED_ORIGINS=https://jdforge.vercel.app,https://jdforge.yourdomain.com

# AI
ANTHROPIC_API_KEY=sk-ant-...

# AWS (for S3)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_S3_BUCKET=jdforge-uploads-prod
AWS_REGION=ap-south-1
```

### 2.2 Frontend Production Environment Variables (Vercel)

```bash
NEXT_PUBLIC_BACKEND_URL=https://api.jdforge.yourdomain.com
```

---

## 3. Deployment Steps

### 3.1 Backend Deployment (Railway / Render)

```bash
# 1. Ensure Procfile or start command is set
uvicorn app.main:app --host 0.0.0.0 --port $PORT

# 2. Set all environment variables in the platform dashboard

# 3. Deploy
git push origin main  # triggers auto-deploy on Railway/Render

# 4. Run migrations post-deploy
alembic upgrade head

# 5. Verify health
curl https://api.jdforge.yourdomain.com/health
# Expected: {"status": "ok", "version": "0.2.0"}
```

### 3.2 Frontend Deployment (Vercel)

```bash
# Vercel auto-deploys on git push to main.
# Ensure these are set in Vercel project settings:
# - NEXT_PUBLIC_BACKEND_URL = https://api.jdforge.yourdomain.com
# - Root directory: frontend

# Manual deploy if needed:
npx vercel --prod
```

### 3.3 Docker Deployment (Optional)

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml (local dev / staging)
version: "3.9"
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
      POSTGRES_DB: jdforge
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  backend:
    build: ./backend
    env_file: ./backend/.env
    ports:
      - "8000:8000"
    depends_on:
      - db

  frontend:
    build: ./frontend
    env_file: ./frontend/.env.local
    ports:
      - "3000:3000"

volumes:
  pgdata:
```

---

## 4. Database Migration Guide

### 4.1 First-Time Setup (Alembic)

```bash
cd backend
pip install alembic

# Initialize alembic
alembic init alembic

# Edit alembic/env.py — import your Base and models:
# from app.db.session import Base
# from app.models import jd  # noqa - registers model
# target_metadata = Base.metadata

# Edit alembic.ini — set sqlalchemy.url:
# sqlalchemy.url = postgresql://...

# Generate first migration
alembic revision --autogenerate -m "initial_jd_schema"

# Apply
alembic upgrade head
```

### 4.2 Adding New Columns / Tables

```bash
# 1. Update your SQLAlchemy model
# 2. Generate migration
alembic revision --autogenerate -m "add_department_to_jd"

# 3. Review the generated migration file in alembic/versions/
# 4. Apply
alembic upgrade head

# 5. Rollback if needed
alembic downgrade -1
```

---

## 5. S3 Migration Guide

### 5.1 Create S3 Bucket

```bash
aws s3 mb s3://jdforge-uploads-prod --region ap-south-1

# Set bucket policy (no public access — use signed URLs)
aws s3api put-public-access-block \
  --bucket jdforge-uploads-prod \
  --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
```

### 5.2 Migrate Existing Local Files

```bash
# Upload all existing local files to S3
aws s3 sync backend/uploads/ s3://jdforge-uploads-prod/uploads/

# Update DB records: file_url from "uploads/file.pdf" → "https://s3.amazonaws.com/jdforge-uploads-prod/uploads/file.pdf"
# Or keep as "uploads/file.pdf" and resolve in backend using S3 presigned URLs
```

### 5.3 Backend Code Changes for S3

```python
# Install boto3
# pip install boto3

import boto3
from botocore.exceptions import ClientError

s3_client = boto3.client("s3", region_name=settings.AWS_REGION)

def generate_presigned_url(object_key: str, expiry: int = 3600) -> str:
    """Generate a time-limited S3 URL for secure file access."""
    return s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.AWS_S3_BUCKET, "Key": object_key},
        ExpiresIn=expiry,
    )
```

---

## 6. Monitoring & Alerting Setup

### 6.1 Uptime Monitoring

```
Service: Uptime Robot (free tier sufficient for start)
Monitor URL: https://api.jdforge.yourdomain.com/health
Check interval: 5 minutes
Alert: Email + Slack on downtime
```

### 6.2 Error Tracking (Sentry)

**Backend:**
```bash
pip install sentry-sdk[fastapi]
```
```python
# In main.py
import sentry_sdk
sentry_sdk.init(dsn="https://...@sentry.io/...", traces_sample_rate=0.1)
```

**Frontend:**
```bash
npm install @sentry/nextjs
npx @sentry/wizard@latest -i nextjs
```

### 6.3 Logging (Structured JSON)

```python
# In main.py
import logging
import json

class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
        })

handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logging.getLogger().addHandler(handler)
```

---

## 7. Rollback Procedures

### 7.1 Backend Rollback

```bash
# Railway/Render — roll back to previous deploy via dashboard

# Manual rollback
git revert HEAD
git push origin main

# DB rollback (if migration was applied)
alembic downgrade -1
```

### 7.2 Frontend Rollback

```bash
# Vercel — "Promote to production" any previous deployment from the dashboard
# Manual:
npx vercel rollback [deployment-url]
```

---

## 8. Incident Response

### Severity Levels

| Level | Description | Response Time |
|---|---|---|
| **P0 — Critical** | Full platform down, data loss | Immediate (< 15 min) |
| **P1 — High** | Core API unavailable, auth broken | < 1 hour |
| **P2 — Medium** | Feature degraded, slow responses | < 4 hours |
| **P3 — Low** | UI bug, minor cosmetic issue | Next sprint |

### On-Call Steps for P0

1. Check `/health` endpoint → determine if backend is up
2. Check database connection → `psql $DATABASE_URL -c "\l"`
3. Check Sentry for exception details
4. Check Vercel/Railway logs for recent errors
5. Rollback to last known-good deployment if issue is from recent deploy
6. Notify stakeholders via Slack/email
7. Write post-mortem within 24 hours

---

## 9. Performance Tuning

### Database Indexes to Add

```sql
-- For filtering by status (future)
CREATE INDEX idx_jd_status ON jd(status);

-- For filtering by department (future)
CREATE INDEX idx_jd_department ON jd(department);

-- For ordering by created_at (already default sort)
CREATE INDEX idx_jd_created_at ON jd(created_at DESC);
```

### Connection Pool Tuning

```python
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,          # Base connections
    max_overflow=20,       # Burst connections
    pool_timeout=30,       # Seconds to wait for a connection
    pool_recycle=1800,     # Recycle connections every 30 min
)
```

---

## 10. Security Hardening Checklist

```bash
# 1. Add rate limiting
pip install slowapi

# 2. Add file validation on upload
pip install python-magic  # MIME type detection

# 3. Scan dependencies for vulnerabilities
pip install safety
safety check -r requirements.txt

# 4. Frontend dependency audit
cd frontend && npm audit

# 5. Ensure no secrets in git history
git log --all --full-history -- '*.env'
git-secrets --scan-history  # if git-secrets is installed
```

---

## 11. Backup Strategy

| Data | Backup Method | Frequency | Retention |
|---|---|---|---|
| PostgreSQL DB | pg_dump → S3 | Daily automated | 30 days |
| S3 file uploads | S3 Versioning enabled | Continuous | 90 days |
| Application config | Git (no secrets) | On change | Indefinite |
| Secrets | Secrets Manager audit | On change | 90 days |

```bash
# Manual DB backup
pg_dump $DATABASE_URL | gzip > backup_$(date +%Y%m%d).sql.gz
aws s3 cp backup_$(date +%Y%m%d).sql.gz s3://jdforge-backups/db/
```

---

## 12. Contacts & Escalation

| Role | Responsibility |
|---|---|
| **Backend Tech Lead** | API, Database, Infrastructure |
| **Frontend Tech Lead** | Next.js, UI, Vercel |
| **DevOps / Infra** | CI/CD, Docker, Cloud |
| **Product Owner** | Business decisions, stakeholder comm |
| **On-Call Engineer** | P0/P1 incident response |
