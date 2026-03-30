# Agentic Medical Voice Agent

An AI-powered voice agent for medical appointment scheduling. Patients interact through natural voice conversations to identify themselves, describe symptoms, receive triage recommendations, and book appointments — all without human intervention.

Built with **Vapi.ai** for voice orchestration, **FastAPI** for backend logic, **Next.js** for the admin dashboard, and **Supabase** (PostgreSQL) for data persistence.

## How It Works

```
Patient calls in
  → Identify (new or returning patient via 9-digit UIN)
  → Triage (symptom collection → specialty matching with follow-up questions)
  → Find Slots (compute available times from doctor schedules)
  → Book / Reschedule / Cancel
  → Transcript saved to database
```

The voice agent uses Vapi tool calling to invoke backend endpoints at each step. Slots are computed on-the-fly from weekly availability templates — no cron jobs or pre-generated data.

## Tech Stack

| Layer    | Technology                                    |
| -------- | --------------------------------------------- |
| Voice AI | Vapi.ai (server URL + tool calling)           |
| Backend  | FastAPI, Pydantic, uvicorn                    |
| Frontend | Next.js 16 (App Router), React 19, TypeScript |
| Styling  | Tailwind CSS v4, shadcn/ui, Radix UI          |
| Data     | TanStack Query, React Hook Form, Zod          |
| Database | Supabase (PostgreSQL)                         |
| Tooling  | uv (Python), pnpm (Node), Ruff, ESLint        |

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── vapi_tools/        # Voice agent tool endpoints
│   │   │   │   ├── identify_patient.py
│   │   │   │   ├── triage.py
│   │   │   │   ├── find_slots.py
│   │   │   │   ├── book.py
│   │   │   │   ├── reschedule.py
│   │   │   │   └── cancel.py
│   │   │   ├── admin/             # Admin CRUD endpoints
│   │   │   ├── vapi_webhook.py    # Call lifecycle events & transcripts
│   │   │   └── vapi_helpers.py    # Payload parsing & signature verification
│   │   ├── services/
│   │   │   ├── slot_engine.py     # Availability computation
│   │   │   ├── triage_engine.py   # Symptom → specialty scoring
│   │   │   └── time_utils.py      # NLP date parsing & voice formatting
│   │   ├── main.py
│   │   ├── config.py
│   │   └── supabase.py
│   ├── schema.sql
│   ├── seed.sql
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── app/                   # Next.js App Router pages
│   │   ├── components/            # shadcn/ui + domain components
│   │   ├── hooks/                 # Auth & data hooks
│   │   └── lib/api/               # API client & types
│   └── package.json
└── supabase/
    └── schema.sql                 # Full database schema
```

## Prerequisites

- Python 3.12+
- Node.js 18+ (LTS recommended)
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [pnpm](https://pnpm.io/) (Node package manager)
- A [Supabase](https://supabase.com/) project
- A [Vapi.ai](https://vapi.ai/) account

## Quick Start

### 1. Clone and configure

```bash
git clone <repo-url>
cd Agentic-Medical-Voice-Agent
```

Copy the example environment files:

```bash
# Backend
cp .env.example .env

# Frontend
cp frontend/.env.local.example frontend/.env.local
```

### 2. Set up the database

Run the schema in your Supabase project:

```bash
# Option A: Paste supabase/schema.sql into the Supabase SQL Editor

# Option B: psql
psql "$SUPABASE_DB_URL" -f supabase/schema.sql
```

Optionally load seed data for local development:

```bash
psql "$SUPABASE_DB_URL" -f backend/seed.sql
```

### 3. Start the backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

The API will be available at **http://localhost:8000**.

To expose the backend to Vapi (required for voice agent tool calls):

```bash
ngrok http 8000
```

### 4. Start the frontend

```bash
cd frontend
pnpm install
pnpm dev
```

The admin dashboard will be available at **http://localhost:3000**.

## Environment Variables

### Backend (`.env` at project root)

| Variable                      | Default                 | Description                              |
| ----------------------------- | ----------------------- | ---------------------------------------- |
| `PROJECT_NAME`                | `FastAPI App`           | Displayed in OpenAPI docs                |
| `ENVIRONMENT`                 | `local`                 | `local`, `staging`, or `production`      |
| `SECRET_KEY`                  | _(random)_              | JWT signing key (must be strong in prod) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `11520`                 | Token lifetime in minutes                |
| `SUPABASE_URL`                | —                       | Supabase project URL                     |
| `SUPABASE_SERVICE_ROLE_KEY`   | —                       | Supabase service role secret key         |
| `CLINIC_TIMEZONE`             | `America/Chicago`       | Timezone for slot computation            |
| `SCHEDULING_HORIZON_DAYS`     | `14`                    | How far ahead patients can book          |
| `VAPI_WEBHOOK_SECRET`         | —                       | Optional Vapi signature verification     |
| `FRONTEND_HOST`               | `http://localhost:3000` | Added to CORS origins automatically      |
| `BACKEND_CORS_ORIGINS`        | `[]`                    | JSON array or comma-separated URLs       |

### Frontend (`frontend/.env.local`)

| Variable                   | Default                 | Description             |
| -------------------------- | ----------------------- | ----------------------- |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | Backend API base URL    |
| `NEXT_PUBLIC_APP_NAME`     | `App`                   | Display name (optional) |

## API Endpoints

### Vapi Tool Endpoints

| Method | Path                                  | Description                         |
| ------ | ------------------------------------- | ----------------------------------- |
| POST   | `/api/v1/vapi/tools/identify-patient` | Patient lookup / registration       |
| POST   | `/api/v1/vapi/tools/triage`           | Symptom → specialty matching        |
| POST   | `/api/v1/vapi/tools/find-slots`       | Compute available appointment slots |
| POST   | `/api/v1/vapi/tools/book`             | Book an appointment                 |
| POST   | `/api/v1/vapi/tools/find-appointment` | Find an existing appointment        |
| POST   | `/api/v1/vapi/tools/reschedule`       | Find replacement slots              |
| POST   | `/api/v1/vapi/tools/reschedule-finalize` | Finalize a reschedule            |
| POST   | `/api/v1/vapi/tools/cancel`           | Cancel an appointment               |
| POST   | `/api/v1/vapi/tools/list-specialties` | List all specialties (fallback)     |
| POST   | `/api/v1/vapi/events`                 | Webhook for call lifecycle events   |

### Admin Endpoints

| Method          | Path                                     | Description                    |
| --------------- | ---------------------------------------- | ------------------------------ |
| GET/POST        | `/api/v1/admin/doctors`                  | List / create doctors          |
| GET/PUT         | `/api/v1/admin/doctors/:id/availability` | Manage weekly schedules        |
| POST/GET/DELETE | `/api/v1/admin/doctors/:id/blocks`       | Manage time-off blocks         |
| GET             | `/api/v1/admin/patients`                 | List / search patients         |
| GET             | `/api/v1/admin/appointments`             | List appointments (filterable) |
| GET             | `/health`                                | Health check                   |

## Database Schema

9 core tables in Supabase (PostgreSQL):

- **specialties** — Medical specialty lookup
- **symptom_specialty_map** — Symptom-to-specialty mapping with weights and follow-up questions
- **doctors** — Doctor profiles
- **doctor_specialties** — Doctor ↔ specialty links (many-to-many)
- **doctor_availability** — Weekly schedule templates (day, start/end time, slot duration)
- **doctor_blocks** — One-off unavailability periods
- **patients** — Patient records identified by 9-digit UIN
- **appointments** — Booked appointments with triage data and follow-up links
- **conversations** — Vapi call transcripts and summaries

See `supabase/schema.sql` for the full schema.

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

## License

MIT
