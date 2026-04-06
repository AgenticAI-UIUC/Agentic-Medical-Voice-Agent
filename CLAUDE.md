# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Agentic Medical Voice Agent — a phone-based medical scheduling system where patients call in, speak to a Vapi.ai voice agent, and the agent books/reschedules/cancels appointments via a FastAPI backend backed by Supabase (PostgreSQL). An admin dashboard (Next.js) lets staff manage doctors, patients, and appointments.

## Commands

### Backend (Python, uses `uv`)
```bash
cd backend
uv sync                              # install dependencies
uv run uvicorn app.main:app --reload  # run dev server on :8000
uv run pytest                         # run all tests
uv run pytest tests/test_emergency_classifier.py  # run single test file
ngrok http 8000                       # expose to Vapi (local dev)
```

### Frontend (Next.js, uses `pnpm`)
```bash
cd frontend
pnpm install        # install dependencies
pnpm dev            # dev server on :3000
pnpm build          # production build
pnpm lint           # ESLint
pnpm typecheck      # TypeScript type checking
```

### Database
```bash
psql "$SUPABASE_DB_URL" -f backend/schema.sql  # apply schema
psql "$SUPABASE_DB_URL" -f backend/seed.sql    # seed data
```

### Pre-commit
Ruff check/format runs automatically on backend Python files via `.pre-commit-config.yaml`.

## Architecture

```
Patient (Phone) ↔ Vapi.ai (Voice + LLM + Tool Calling) ↔ FastAPI Backend ↔ Supabase/PostgreSQL
                                                                                    ↕
                                                                        Next.js Admin Dashboard
```

### Three conversation flows
1. **New Appointment** — identify/register patient → collect symptoms → triage (confidence-based specialty matching) → find available slots → book
2. **Reschedule** — identify patient → find existing appointment → collect new preferences → find new slots → atomic swap (book new + cancel old)
3. **Cancel** — identify patient → find appointment → confirm → cancel

### Backend (`backend/app/`)
- **`main.py`** — FastAPI entry point (CORS, lifespan)
- **`api/vapi_tools/`** — Vapi tool endpoints (identify, triage, find-slots, book, reschedule, cancel). Thin routes that parse Vapi payloads and delegate to services.
- **`api/vapi_webhook.py`** — End-of-call webhook, saves transcripts to `conversations` table
- **`api/vapi_helpers.py`** — Vapi payload parsing, phone/UIN normalization
- **`api/admin/routes.py`** — Admin CRUD for doctors, patients, appointments (no auth yet)
- **`services/triage_engine.py`** — Weighted symptom→specialty scoring from `symptom_specialty_map` table. ≥60% confidence → determined. Includes emergency red-flag detection (regex-based: cardiac, stroke, respiratory, bleeding, consciousness, anaphylaxis, mental health, poisoning).
- **`services/slot_engine.py`** — Stateless on-the-fly slot computation: weekly availability templates minus booked appointments minus one-off blocks. Supports NLP day preferences and time buckets (morning/afternoon/any). Returns up to 5 slots.
- **`services/time_utils.py`** — NLP date parsing ("tomorrow", "next Monday", specific dates), timezone conversion (UTC storage, clinic-local display), voice-friendly formatting.

### Frontend (`frontend/src/`)
- Next.js 16 App Router with React 19, TypeScript, Tailwind CSS v4, shadcn/ui
- TanStack Query v5 for data fetching, React Hook Form + Zod for forms
- `lib/api/client.ts` — fetch wrapper with ApiError handling
- `hooks/` — auth and user CRUD hooks

### Database (9 tables)
Key tables: `specialties`, `symptom_specialty_map`, `doctors`, `doctor_availability`, `doctor_blocks`, `patients`, `appointments`, `conversations`. Schema in `backend/schema.sql`, seed data in `backend/seed.sql`.

## Key Design Decisions

- **Stateless slot computation** — no cron jobs; slots computed fresh every request from templates minus bookings minus blocks
- **Backend validates everything** — voice agent doesn't validate phone numbers, count digits, or check formats; backend returns clear errors for agent to relay
- **Atomic rescheduling** — single transaction books new + cancels old to prevent partial failures
- **Timezone-aware** — UTC storage, display in clinic timezone (`CLINIC_TIMEZONE` env var, default `America/Chicago`)
- **9-digit UIN** — patient identifier designed to be easy to speak over phone, separate from internal UUIDs
- **Thin routes, fat services** — business logic lives in `triage_engine`, `slot_engine`, `time_utils`

## Vapi Integration

The system prompt for the voice agent is in `Medical Voice Agent — System Prompt.md` (~40KB). It defines the agent's persona, conversation flows, tool-calling behavior, and error handling. All Vapi tool endpoints are under `/api/v1/vapi/tools/`.

## Environment Variables

Backend: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `CLINIC_TIMEZONE`, `SCHEDULING_HORIZON_DAYS`, `FRONTEND_HOST`, `BACKEND_CORS_ORIGINS`, `VAPI_WEBHOOK_SECRET` (optional). See `.env.example`.

Frontend: `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_APP_NAME`. See `frontend/.env.local.example`.
