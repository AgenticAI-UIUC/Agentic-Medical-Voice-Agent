# Full Stack FastAPI + Next.js

A full-stack web application inspired by the official [fastapi/full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template), adapted to use **Next.js (App Router)** for the frontend.

## Tech Stack

| Layer    | Technology                                    |
| -------- | --------------------------------------------- |
| Backend  | FastAPI, Pydantic, PyJWT, uvicorn             |
| Frontend | Next.js 16 (App Router), React 19, TypeScript |
| Styling  | Tailwind CSS v4, shadcn/ui, Radix UI          |
| Data     | TanStack Query, React Hook Form, Zod          |
| Voice AI | Vapi (server URL + tool calling)              |
| Database | Supabase (Postgres)                           |
| Tooling  | uv (Python), pnpm (Node), Ruff, ESLint        |

## Prerequisites

- Python 3.12+
- Node.js 18+ (LTS recommended)
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [pnpm](https://pnpm.io/) (Node package manager)

## Quick Start

### 1. Clone and configure

```bash
git clone <repo-url> full-stack-fastapi
cd full-stack-fastapi
```

Copy the example environment files:

```bash
# Backend (project root)
cp .env.example .env

# Frontend
cp frontend/.env.local.example frontend/.env.local
```

### 2. Start the backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

```bash
ngrok http 8000
```

The API will be available at **http://localhost:8000**. Swagger docs are at `/api/v1/openapi.json` (local environment only).

### 3. Start the frontend

```bash
cd frontend
pnpm install
pnpm dev
```

The frontend will be available at **http://localhost:3000**.

## Environment Variables

### Backend (`.env` at project root)

| Variable                      | Default                 | Description                              |
| ----------------------------- | ----------------------- | ---------------------------------------- |
| `PROJECT_NAME`                | `FastAPI App`           | Displayed in OpenAPI docs                |
| `ENVIRONMENT`                 | `local`                 | `local`, `staging`, or `production`      |
| `SECRET_KEY`                  | _(random)_              | JWT signing key (must be strong in prod) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60`                    | Token lifetime in minutes                |
| `FRONTEND_HOST`               | `http://localhost:5173` | Added to CORS origins automatically      |
| `BACKEND_CORS_ORIGINS`        | `[]`                    | JSON array or comma-separated URLs       |
| `SUPABASE_URL`                | —                       | Supabase project URL                     |
| `SUPABASE_SERVICE_ROLE_KEY`   | —                       | Supabase service role secret key         |

### Frontend (`frontend/.env.local`)

| Variable                   | Default                 | Description             |
| -------------------------- | ----------------------- | ----------------------- |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | Backend API base URL    |
| `NEXT_PUBLIC_APP_NAME`     | `App`                   | Display name (optional) |

## Default Accounts (Local Only)

Seed data is only loaded when `ENVIRONMENT=local`.

| Email             | Password      | Role      |
| ----------------- | ------------- | --------- |
| admin@example.com | changethis123 | Superuser |
| alice@example.com | password123   | Regular   |

## Running Tests

```bash
# Backend
cd backend
uv run pytest

# Frontend
cd frontend
pnpm typecheck
pnpm lint
```

## Database Schema Bootstrap (Supabase)

To help new contributors reproduce your database structure, this repo includes a bootstrap SQL script:

- `supabase/schema.sql`

You can run it in one of two ways:

```bash
# Option 1: Supabase SQL Editor
# Open supabase/schema.sql, paste into SQL editor, run.

# Option 2: psql
psql "$SUPABASE_DB_URL" -f supabase/schema.sql
```

This script creates all the tables and constraints used by the app, including the circular relationship between `appointments` and `appointment_slots`.

## License

MIT
