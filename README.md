# Hiring Platform

A full-stack hiring platform for generating, reviewing, publishing, and sourcing job descriptions.

## Repository Layout

```text
backend/    FastAPI API, database models, PDF generation, LLM providers, and Zoho sourcing services
frontend/   Next.js app router frontend
```

## Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL

## Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

The API runs at `http://127.0.0.1:8000` by default.

## Frontend

```bash
cd frontend
npm install
copy .env.example .env.local
npm run dev
```

The web app runs at `http://localhost:3000`.

## Useful Commands

```bash
# frontend
npm run lint
npm run build

# backend
python seed.py
```

## Notes

- Runtime uploads are written to `backend/uploads/` and are intentionally ignored by Git.
- Local environment files are ignored. Use the `.env.example` files as templates.
- Generated caches such as `__pycache__`, `.next`, `node_modules`, and TypeScript build info should not be committed.
