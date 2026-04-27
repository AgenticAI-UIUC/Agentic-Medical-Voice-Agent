# Agentic Medical Voice Agent

An AI-powered voice agent for medical appointment scheduling. Patients interact through natural voice conversations to identify themselves, describe symptoms, receive triage recommendations, and book appointments — all without human intervention.

Built with **Vapi.ai** for voice orchestration, **FastAPI** for backend logic, **Next.js** for the admin dashboard, and **Supabase** (PostgreSQL) for data persistence.

## Live Demo

[Live Demo Presentation](https://docs.google.com/presentation/d/1cgQ5Le6WUlc7gRtGxONqgf50JMEoKzHeZP6AZMr_YFc/edit?slide=id.g3de75b2e283_0_1#slide=id.g3de75b2e283_0_1)

### Production URLs

- Frontend: https://medicalvoiceagentfrontend.vercel.app
- Backend: https://medicalvoiceagentbackend.vercel.app

## Deploy to Vercel

Both apps are already linked to Vercel projects through their local `.vercel/`
folders:

- Backend: `medical_voice_agent_back_end`
- Frontend: `medical_voice_agent_front_end`

Deploy the latest backend first, then the frontend:

```bash
# From the repo root
cd backend
vercel --prod

cd ../frontend
vercel --prod
```

If the Vercel CLI is not installed globally, use:

```bash
cd backend
pnpm dlx vercel --prod

cd ../frontend
pnpm dlx vercel --prod
```

Before deploying, confirm the production environment variables in Vercel:

- Backend: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `FRONTEND_HOST`,
  `BACKEND_CORS_ORIGINS`, and optional `VAPI_WEBHOOK_SECRET`
- Frontend: `NEXT_PUBLIC_API_BASE_URL` should point to the production backend,
  for example `https://medicalvoiceagentbackend.vercel.app`

### Demo Login

| Email               | Password |
| ------------------- | -------- |
| `admin@example.com` | `12345678` |

## How It Works

```
Patient calls in
  → Identify (new or returning patient via 9-digit UIN)
  → Triage (keyword matching + optional semantic search → specialty matching)
  → Find Slots (compute available times from doctor schedules)
  → Book / Reschedule / Cancel
  → Transcript saved to database
```

The voice agent uses Vapi tool calling to invoke backend endpoints at each step. Slots are computed on-the-fly from weekly availability templates — no cron jobs or pre-generated data.

Semantic triage is optional. When enabled, the backend embeds the patient's
natural-language symptom description, searches the `medical_knowledge` pgvector
table, and blends those semantic matches with the existing
`symptom_specialty_map` keyword scores.

Privacy rule: the voice assistant is self-service only. If a caller says they are acting for someone else, it should refuse to look up, book, reschedule, or cancel that other person's appointment and offer transfer to staff instead.

## Conversation Workflows

### New Appointment (Booking)

```
Patient: "I'd like to make an appointment"
  │
  ├─ Follow-up appointment?
  │   ├─ Yes → Skip new/returning question → Collect UIN → identify_patient
  │   └─ No  → continue below
  │
  ├─ New patient?
  │   ├─ Yes → Say "Before I schedule that appointment, I need a few details to set you up." → Collect confirmed UIN, name, confirmed phone → register_patient
  │   └─ No  → Collect UIN → identify_patient
  │
  │  After identify/register: continue the booking flow directly
  │  Do not reset with "What can I help you with today?"
  │  If newly registered this call, skip follow-up screening and go straight to symptoms
  │  If a new-patient registration attempt returns `ALREADY_EXISTS`, treat it as a duplicate UIN case
  │  If the UIN belongs to the wrong person and the caller denies that identity, keep the collected name/phone, confirm the corrected UIN, and retry `register_patient`
  │  Shared phone numbers are allowed; do not treat a repeated phone number as a registration conflict
  │  After the caller confirms a UIN readback, do not do a second digit-count check yourself; let the tool response validate it
  │  If the caller already said this is a follow-up, preserve that and go straight into follow-up details after identification
  │  Do not call register_patient until all required fields are collected
  │
  ▼
Symptom Collection
  │  "Can you describe your symptoms?"
  │  "Do you have a specialist preference?"
  │
  ▼
Triage Loop (up to 2 rounds)
  │  Call triage with symptoms
  │  ├─ Confidence ≥ 60% → Specialty determined
  │  └─ Confidence < 60% → Ask follow-up questions → re-triage
  │
  │  If still undetermined after 2 rounds:
  │  └─ Use patient's preferred specialty, or recommend General Practice first via list_specialties
  │
  ▼
Specialty Confirmation
  │  Compare triage result with patient's preference
  │  ├─ Match → Confirm
  │  └─ Differ → Ask patient which they prefer
  │
  ▼
Find Slots
  │  "How soon would you like to be seen?"
  │  "Morning or afternoon?"
  │  Call find_slots → Present up to 3 options
  │  ├─ Slots found → Patient picks one
  │  └─ No slots → Suggest wider time window → retry
  │
  ▼
Book Appointment
  │  Call book → Confirmation
  │  "You're booked with Dr. [name] on [day] at [time]."
  │
  ▼
End of call → Transcript saved via webhook
```

### Reschedule

```
Patient: "I'd like to reschedule"
  │  (Skip "have you been here before?" — rescheduling implies returning patient)
  │
  ▼
Identify Patient (UIN → identify_patient)
  │
  ▼
Find Appointment (find_appointment)
  │  If the caller says "I don't remember which one",
  │  call find_appointment with just patient_id
  │  ├─ Single match → Confirm with patient
  │  ├─ Multiple → List options, patient picks one,
  │  │             briefly restate the chosen doctor/date/time,
  │  │             then ask for reschedule preferences
  │  └─ None found → Offer to book new
  │
  ▼
Collect Preferences
  │  "When would you like to reschedule to?"
  │  "Morning or afternoon?"
  │
  ▼
Find New Slots (reschedule)
  │  ├─ Slots found → Patient picks one
  │  └─ No slots → Ask for different day/time → retry
  │
  ▼
Finalize (reschedule_finalize)
  │  Atomically: book new slot + cancel old appointment
  │  "You're now booked with Dr. [name] on [day] at [time].
  │   Your previous appointment has been cancelled."
```

### Cancel

```
Patient: "I'd like to cancel"
  │
  ▼
Identify Patient → Find Appointment
  │  (Same as reschedule flow)
  │
  ▼
Confirm Cancellation
  │  "Are you sure you'd like to cancel?"
  │  ├─ Yes → Call cancel → "Your appointment has been cancelled."
  │  └─ No  → "No problem, your appointment stays as is."
```

## Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│              │     │                  │     │              │
│  Patient     │────▶│  Vapi.ai         │────▶│  FastAPI     │
│  (Phone)     │◀────│  (Voice + LLM)   │◀────│  Backend     │
│              │     │                  │     │              │
└──────────────┘     └──────────────────┘     └──────┬───────┘
                                                     │
                     ┌──────────────────┐     ┌──────▼───────┐
                     │                  │     │              │
                     │  Next.js Admin   │────▶│  Supabase    │
                     │  Dashboard       │◀────│  (PostgreSQL)│
                     │                  │     │              │
                     └──────────────────┘     └──────────────┘
```

**Data flow:**
1. Patient calls → Vapi handles speech-to-text and LLM orchestration
2. Vapi's LLM decides which tool to call based on the system prompt
3. Tool calls hit FastAPI endpoints → query/mutate Supabase
4. Results returned to Vapi → LLM generates spoken response
5. End-of-call webhook saves transcript to database
6. Admin dashboard reads from Supabase for doctor/patient/appointment management

## Key Design Decisions

- **Stateless slot computation.** Available times are computed on every request from weekly templates minus booked appointments and blocks. No cron jobs, no stale pre-generated data.
- **Confidence-based triage.** Symptoms are scored against a weighted mapping table. If the top candidate's confidence exceeds 60%, a specialty is recommended. Otherwise, follow-up questions are asked briefly, then the assistant falls back after 2 rounds to the patient's preference or a General Practice recommendation.
- **Atomic rescheduling.** `reschedule_finalize` books the new slot and cancels the old one in a single operation. If the cancel fails, the patient gets a partial-failure notice instead of a silent error.
- **Timezone-aware formatting.** All times stored in UTC. Voice labels are converted to the clinic's local timezone (`CLINIC_TIMEZONE`) for natural readback — "Wednesday, April 8 at 1 PM" instead of raw ISO strings.
- **Backend validates, not the LLM.** The system prompt tells the voice agent not to count digits or validate phone numbers itself — the backend handles all validation and returns clear error messages for the LLM to relay. The assistant should repeat the tool's actual `message`, not invent a new reason such as claiming a confirmed 9-digit UIN is only 8 digits.

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
│   │   │   ├── admin/             # Protected admin CRUD endpoints
│   │   │   ├── deps.py            # Supabase Auth dependencies
│   │   │   ├── doctors.py         # Authenticated dashboard doctor views
│   │   │   ├── login.py           # Supabase Auth login/logout
│   │   │   ├── users.py           # Staff user/profile management
│   │   │   ├── vapi_webhook.py    # Call lifecycle events & transcripts
│   │   │   └── vapi_helpers.py    # Payload parsing & signature verification
│   │   ├── services/
│   │   │   ├── slot_engine.py     # Availability computation
│   │   │   ├── triage_engine.py   # Symptom → specialty scoring
│   │   │   └── time_utils.py      # NLP date parsing & voice formatting
│   │   ├── main.py
│   │   ├── config.py
│   │   └── supabase.py
│   ├── migrations/                # Incremental database changes
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
└── Medical Voice Agent — System Prompt.md   # Vapi assistant system prompt
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
# Option A: Paste backend/schema.sql into the Supabase SQL Editor

# Option B: psql
psql "$SUPABASE_DB_URL" -f backend/schema.sql
```

Optionally load seed data for local development:

```bash
psql "$SUPABASE_DB_URL" -f backend/seed.sql
```

The seed data includes 10 specialties, 8 doctors with weekly schedules, 50+ symptom mappings, 5 test patients, 4 sample appointments, and 2 doctor blocks.

`backend/seed.sql` sets the SQL session timezone to `America/Chicago` so seeded appointments and doctor blocks represent clinic-local demo times. This keeps the database timestamps aligned with the times the voice agent reads back to callers.

To enable semantic triage, apply the pgvector migration, add
`OPENAI_API_KEY` and `TRIAGE_SEMANTIC_SEARCH_ENABLED=true` to `.env`, then
ingest the starter knowledge chunks:

```bash
psql "$SUPABASE_DB_URL" -f backend/migrations/010_medical_knowledge_rag.sql

cd backend
uv run python -m app.services.ingest_knowledge
```

If you want to wipe only this app's data and reseed without rebuilding the schema, run this in the Supabase SQL Editor first:

```sql
TRUNCATE TABLE
  public.appointments,
  public.conversations,
  public.doctor_blocks,
  public.doctor_availability,
  public.doctor_specialties,
  public.symptom_specialty_map,
  public.patients,
  public.doctors,
  public.specialties
RESTART IDENTITY CASCADE;
```

Then rerun:

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

### 5. Configure Vapi

1. Create an assistant in the [Vapi dashboard](https://dashboard.vapi.ai/)
2. Set the **Server URL** to your ngrok URL (e.g., `https://xxxx.ngrok.io/api/v1`)
3. Paste the contents of `Medical Voice Agent — System Prompt.md` as the system prompt
4. Create each tool listed in the [Vapi Tool Definitions](#vapi-tool-definitions) section below
5. Set the **First Message** to: "Hi, this is Jane from the clinic. How can I help you today?"

## Environment Variables

### Backend (`.env` at project root)

| Variable                      | Default                 | Description                              |
| ----------------------------- | ----------------------- | ---------------------------------------- |
| `PROJECT_NAME`                | `FastAPI App`           | Displayed in OpenAPI docs                |
| `ENVIRONMENT`                 | `local`                 | `local`, `staging`, or `production`      |
| `SUPABASE_URL`                | —                       | Supabase project URL                     |
| `SUPABASE_SERVICE_ROLE_KEY`   | —                       | Supabase service role secret key         |
| `CLINIC_TIMEZONE`             | `America/Chicago`       | Timezone for slot computation            |
| `SCHEDULING_HORIZON_DAYS`     | `14`                    | How far ahead patients can book          |
| `VAPI_WEBHOOK_SECRET`         | —                       | Optional Vapi signature verification     |
| `OPENAI_API_KEY`              | —                       | Optional embeddings key for semantic triage |
| `TRIAGE_SEMANTIC_SEARCH_ENABLED` | `false`              | Enables pgvector semantic triage matches |
| `TRIAGE_SEMANTIC_MATCH_COUNT` | `5`                     | Number of semantic chunks to retrieve    |
| `TRIAGE_SEMANTIC_MATCH_THRESHOLD` | `0.3`               | Minimum vector similarity to include     |
| `TRIAGE_SEMANTIC_SCORE_SCALE` | `2.0`                   | Weight multiplier for semantic scores    |
| `FRONTEND_HOST`               | `http://localhost:3000` | Added to CORS origins automatically      |
| `BACKEND_CORS_ORIGINS`        | `[]`                    | JSON array or comma-separated URLs       |

### Frontend (`frontend/.env.local`)

| Variable                   | Default                 | Description             |
| -------------------------- | ----------------------- | ----------------------- |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | Backend API base URL    |
| `NEXT_PUBLIC_APP_NAME`     | `App`                   | Display name (optional) |

## Supabase Auth

The staff dashboard uses Supabase Auth access tokens. Create the first staff user in Supabase Authentication, then set raw app metadata:

```json
{
  "is_active": true,
  "is_superuser": true
}
```

Optional raw user metadata:

```json
{
  "full_name": "Clinic Admin"
}
```

`is_active` gates all dashboard access. `is_superuser` gates user management, patient/admin appointment reads, and doctor schedule mutations.

## API Endpoints

### Vapi Tool Endpoints

All Vapi tool endpoints accept the standard Vapi tool-call payload and return
`{"results": [...]}`.

| Method | Path                                    | Description                         |
| ------ | --------------------------------------- | ----------------------------------- |
| POST   | `/api/v1/vapi/tools/identify-patient`   | Look up patient by UIN              |
| POST   | `/api/v1/vapi/tools/register-patient`   | Register a new patient              |
| POST   | `/api/v1/vapi/tools/triage`             | Symptom → specialty matching        |
| POST   | `/api/v1/vapi/tools/list-specialties`   | List all specialties (fallback)     |
| POST   | `/api/v1/vapi/tools/find-slots`         | Compute available appointment slots |
| POST   | `/api/v1/vapi/tools/book`               | Book an appointment                 |
| POST   | `/api/v1/vapi/tools/find-appointment`   | Find existing appointments          |
| POST   | `/api/v1/vapi/tools/reschedule`         | Find new slots for rescheduling     |
| POST   | `/api/v1/vapi/tools/reschedule-finalize`| Book new + cancel old atomically    |
| POST   | `/api/v1/vapi/tools/cancel`             | Cancel an appointment               |
| POST   | `/api/v1/vapi/events`                   | Webhook for call lifecycle events   |

### Auth and Dashboard Endpoints

| Method       | Path                         | Description                          |
| ------------ | ---------------------------- | ------------------------------------ |
| POST         | `/api/v1/login/access-token` | Sign in with Supabase email/password |
| POST         | `/api/v1/login/logout`       | Revoke current Supabase session      |
| GET/PATCH    | `/api/v1/users/me`           | Read/update current profile          |
| PATCH        | `/api/v1/users/me/password`  | Change current password              |
| GET          | `/api/v1/doctors`            | List dashboard doctor cards          |
| GET          | `/api/v1/doctors/:id/schedule` | Weekly doctor schedule             |
| GET/POST     | `/api/v1/users`              | List/create users (superuser only)   |
| PATCH/DELETE | `/api/v1/users/:id`          | Update/delete users (superuser only) |

### Admin Endpoints

| Method          | Path                                     | Description                    |
| --------------- | ---------------------------------------- | ------------------------------ |
| GET/POST        | `/api/v1/admin/doctors`                  | List / create doctors          |
| GET/PUT         | `/api/v1/admin/doctors/:id/availability` | Manage weekly schedules        |
| POST/GET/DELETE | `/api/v1/admin/doctors/:id/blocks`       | Manage time-off blocks         |
| GET             | `/api/v1/admin/patients`                 | List / search patients         |
| GET             | `/api/v1/admin/appointments`             | List appointments (filterable) |
| GET             | `/health`                                | Health check                   |

Admin endpoints require a bearer token. Doctor reads require an active user; doctor mutations and patient/appointment admin reads require `is_superuser=true`.

## Database Schema

10 core tables in Supabase (PostgreSQL):

```
specialties ◀── symptom_specialty_map
    ▲
    │
doctor_specialties ──▶ doctors ◀── doctor_availability
                         ▲            doctor_blocks
                         │
                    appointments ──▶ patients
                         │              ▲
                         ▼              │
                    conversations ──────┘

medical_knowledge stores embedded triage chunks for optional semantic search.
```

| Table                  | Description                                                    |
| ---------------------- | -------------------------------------------------------------- |
| **specialties**        | Medical specialty lookup (e.g., Cardiology, Dermatology)       |
| **symptom_specialty_map** | Symptom → specialty mapping with weights and follow-up questions |
| **medical_knowledge**  | Embedded triage knowledge chunks for semantic search             |
| **doctors**            | Doctor profiles (name, image, active status)                   |
| **doctor_specialties** | Doctor ↔ specialty links (many-to-many)                        |
| **doctor_availability**| Weekly schedule templates (day, start/end time, slot duration)  |
| **doctor_blocks**      | One-off unavailability periods (conferences, time off)         |
| **patients**           | Patient records identified by 9-digit UIN                      |
| **appointments**       | Booked appointments with triage data and follow-up links |
| **conversations**      | Vapi call transcripts (JSON) and AI-generated summaries        |

See `backend/schema.sql` for the full schema.

## Triage Engine

The triage engine matches patient symptoms to medical specialties using a weighted scoring system.

**How it works:**

1. Patient symptoms are matched against the `symptom_specialty_map` table (case-insensitive partial match)
2. Weights are summed per specialty across all matched symptoms
3. Scores are normalized to a 0–1 confidence scale
4. If the top candidate's confidence is ≥ 60%, the specialty is returned
5. Otherwise, follow-up questions are extracted from the top candidates and sent back to the voice agent

**Example:**

```
Symptoms: "chest pain, shortness of breath"

  chest pain        → Cardiology (2.0), Emergency Medicine (1.5)
  shortness of breath → Cardiology (1.5), Pulmonology (1.5)

  Cardiology total:  3.5  →  confidence ≈ 70%  →  SPECIALTY_FOUND
  Pulmonology total: 1.5
```

The triage loop runs up to 2 times. If no specialty is determined after 2 rounds, the system falls back to the patient's stated preference or lists specialties with a preference for recommending General Practice as the safest general starting point.

## Slot Engine

The slot engine computes available appointment times on-the-fly from weekly templates.

**Algorithm:**

1. Parse the patient's preferred day (natural language: "tomorrow", "next Monday", "this week") into a date range
2. Parse their time preference into a bucket (morning: 8 AM–12 PM, afternoon: 12–5 PM, or any)
3. For each doctor with the target specialty:
   - Fetch their weekly availability templates
   - Generate all theoretical slots in the date range
   - Subtract booked appointments and doctor blocks
   - Filter by time bucket
4. Return up to 5 slots sorted by start time, with voice-friendly labels

**Natural language date parsing** supports: today, tomorrow, this week, next week, next Monday, weekend, specific dates (3/24, March 24), and relative ranges (2 weeks).

## Vapi Tool Definitions

These are the tools configured in the Vapi dashboard. Each tool calls a backend endpoint via Vapi's server URL.

Prompt/tool alignment note: if the live assistant still self-validates UIN length, repeats a UIN confirmation twice in the same turn, or invents `INVALID` reasons after you update this repo, refresh the system prompt in the Vapi dashboard so the hosted assistant matches the checked-in prompt.

### identify_patient

Look up an existing patient by their 9-digit university UIN. Returns the patient record if found, or an error if the UIN is invalid or not registered.

```json
{
  "type": "object",
  "properties": {
    "uin": {
      "type": "string",
      "description": "The patient's 9-digit university identification number"
    }
  },
  "required": ["uin"]
}
```

### register_patient

Register a new patient in the system with their UIN, name, and phone number.

Call this only after the assistant has already collected all three required fields: confirmed `uin`, `full_name`, and confirmed `phone`.

If a new-patient flow hits `ALREADY_EXISTS`, treat it as a duplicate-UIN case: confirm the corrected UIN and retry `register_patient` with the already collected name/phone. Shared phone numbers are allowed and should not block registration.

```json
{
  "type": "object",
  "properties": {
    "uin": {
      "type": "string",
      "description": "The patient's 9-digit university identification number"
    },
    "full_name": {
      "type": "string",
      "description": "The patient's full name"
    },
    "phone": {
      "type": "string",
      "description": "The patient's phone number (any length)"
    },
    "email": {
      "type": "string",
      "description": "The patient's email address (optional)"
    },
    "allergies": {
      "type": "string",
      "description": "Any known allergies (optional)"
    }
  },
  "required": ["uin", "full_name", "phone"]
}
```

### triage

Analyze patient symptoms to determine the appropriate medical specialty. May return follow-up questions if more information is needed.

```json
{
  "type": "object",
  "properties": {
    "symptoms": {
      "type": "string",
      "description": "Comma-separated list of the patient's symptoms"
    },
    "description": {
      "type": "string",
      "description": "The patient's full natural-language symptom description, preserving their original wording when possible"
    },
    "answers": {
      "type": "object",
      "description": "Answers to follow-up triage questions from a previous triage call (optional)"
    }
  },
  "required": ["symptoms"]
}
```

### list_specialties

List all available medical specialties. Used as a fallback when triage cannot determine a specialty. When General Practice is available, the assistant should prefer recommending it first as a safe general entry point because a GP can evaluate the patient and route them to a specialist if needed.

```json
{
  "type": "object",
  "properties": {}
}
```

### find_slots

Find available appointment slots for a given specialty or doctor within a preferred time window.

```json
{
  "type": "object",
  "properties": {
    "specialty_id": {
      "type": "string",
      "description": "The specialty ID to find slots for (for new appointments)"
    },
    "doctor_id": {
      "type": "string",
      "description": "The doctor ID to find slots for (for follow-ups)"
    },
    "preferred_day": {
      "type": "string",
      "description": "Preferred day or time range, e.g. 'tomorrow', 'next Monday', 'this week', 'as soon as possible', or 'soonest available'"
    },
    "preferred_time": {
      "type": "string",
      "description": "Preferred time of day, e.g. 'morning', 'afternoon', 'any'"
    }
  }
}
```

### book

Book a confirmed appointment for a patient with a specific doctor and time slot.

```json
{
  "type": "object",
  "properties": {
    "patient_id": {
      "type": "string",
      "description": "The patient's ID"
    },
    "doctor_id": {
      "type": "string",
      "description": "The doctor's ID"
    },
    "start_at": {
      "type": "string",
      "description": "ISO 8601 datetime for appointment start"
    },
    "end_at": {
      "type": "string",
      "description": "ISO 8601 datetime for appointment end"
    },
    "specialty_id": {
      "type": "string",
      "description": "The specialty ID (optional)"
    },
    "follow_up_from_id": {
      "type": "string",
      "description": "The original appointment ID if this is a follow-up (optional)"
    },
    "reason": {
      "type": "string",
      "description": "Reason for the appointment (optional)"
    },
    "symptoms": {
      "type": "string",
      "description": "Patient's symptoms (optional)"
    },
    "urgency": {
      "type": "string",
      "description": "Urgency level: ROUTINE, URGENT, or ER (default: ROUTINE)"
    }
  },
  "required": ["patient_id", "doctor_id", "start_at", "end_at"]
}
```

### find_appointment

Find existing confirmed appointments for a patient, optionally filtered by doctor name or reason.

```json
{
  "type": "object",
  "properties": {
    "patient_id": {
      "type": "string",
      "description": "The patient's ID"
    },
    "doctor_name": {
      "type": "string",
      "description": "Doctor's name to filter by (optional)"
    },
    "reason": {
      "type": "string",
      "description": "Reason or symptoms to filter by (optional)"
    },
    "include_past": {
      "type": "boolean",
      "description": "Set to true for follow-up lookups when the original appointment may be a past completed visit (optional)"
    }
  },
  "required": ["patient_id"]
}
```

### reschedule

Find new available slots for rescheduling an existing appointment. Does not finalize the reschedule — use reschedule_finalize to confirm the new slot.

```json
{
  "type": "object",
  "properties": {
    "appointment_id": {
      "type": "string",
      "description": "The appointment ID to reschedule"
    },
    "patient_id": {
      "type": "string",
      "description": "The patient's ID from identification (recommended when available)"
    },
    "preferred_day": {
      "type": "string",
      "description": "Preferred day or time range for the new appointment"
    },
    "preferred_time": {
      "type": "string",
      "description": "Preferred time of day for the new appointment"
    }
  },
  "required": ["appointment_id"]
}
```

### reschedule_finalize

Atomically book a new appointment and cancel the original one in a single step. Used after the patient picks a new slot from the reschedule results.

```json
{
  "type": "object",
  "properties": {
    "original_appointment_id": {
      "type": "string",
      "description": "The ID of the appointment being rescheduled"
    },
    "patient_id": {
      "type": "string",
      "description": "The patient's ID"
    },
    "doctor_id": {
      "type": "string",
      "description": "The doctor's ID for the new appointment"
    },
    "start_at": {
      "type": "string",
      "description": "ISO 8601 datetime for the new appointment start"
    },
    "end_at": {
      "type": "string",
      "description": "ISO 8601 datetime for the new appointment end"
    },
    "specialty_id": {
      "type": "string",
      "description": "The specialty ID (optional, inherited from original if omitted)"
    },
    "reason": {
      "type": "string",
      "description": "Reason for appointment (optional, inherited from original if omitted)"
    }
  },
  "required": ["original_appointment_id", "patient_id", "doctor_id", "start_at", "end_at"]
}
```

### cancel

Cancel a confirmed appointment.

```json
{
  "type": "object",
  "properties": {
    "appointment_id": {
      "type": "string",
      "description": "The appointment ID to cancel"
    }
  },
  "required": ["appointment_id"]
}
```

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

## Git Hooks

This repo includes a native Git pre-commit hook in `.githooks/pre-commit` that blocks commits when the backend test suite fails.

Set it up once per clone:

```bash
git config core.hooksPath .githooks
```

The hook runs `./scripts/run_backend_tests.sh`, which prefers `backend/.venv` and falls back to `uv run --directory backend pytest tests`.

## License

MIT
