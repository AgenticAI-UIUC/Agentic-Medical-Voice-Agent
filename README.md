# Agentic Medical Voice Agent

An AI-powered voice agent for medical appointment scheduling. Patients interact through natural voice conversations to identify themselves, describe symptoms, receive triage recommendations, and book appointments — all without human intervention.

Built with **Vapi.ai** for voice orchestration, **FastAPI** for backend logic, **Next.js** for the admin dashboard, and **Supabase** (PostgreSQL) for data persistence.

## Live Demo

[Live Demo Presentation](https://docs.google.com/presentation/d/1cgQ5Le6WUlc7gRtGxONqgf50JMEoKzHeZP6AZMr_YFc/edit?slide=id.g3de75b2e283_0_1#slide=id.g3de75b2e283_0_1)

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
  │  "On a scale of 1-10, how severe?"
  │  "Do you have a specialist preference?"
  │
  ▼
Triage Loop (up to 5 rounds)
  │  Call triage with symptoms
  │  ├─ Confidence ≥ 60% → Specialty determined
  │  └─ Confidence < 60% → Ask follow-up questions → re-triage
  │
  │  If still undetermined after 5 rounds:
  │  └─ Use patient's preferred specialty, or list_specialties for manual pick
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
- **Confidence-based triage.** Symptoms are scored against a weighted mapping table. If the top candidate's confidence exceeds 60%, a specialty is recommended. Otherwise, follow-up questions are asked (up to 5 rounds).
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

### Admin Endpoints

| Method         | Path                                      | Description                  |
| -------------- | ----------------------------------------- | ---------------------------- |
| GET/POST       | `/api/v1/admin/doctors`                   | List / create doctors        |
| GET/PUT        | `/api/v1/admin/doctors/:id/availability`  | Manage weekly schedules      |
| POST/GET/DELETE| `/api/v1/admin/doctors/:id/blocks`        | Manage time-off blocks       |
| GET            | `/api/v1/admin/patients`                  | List / search patients       |
| GET            | `/api/v1/admin/appointments`              | List appointments (filterable) |
| GET            | `/health`                                 | Health check                 |

## Database Schema

9 core tables in Supabase (PostgreSQL):

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
```

| Table                  | Description                                                    |
| ---------------------- | -------------------------------------------------------------- |
| **specialties**        | Medical specialty lookup (e.g., Cardiology, Dermatology)       |
| **symptom_specialty_map** | Symptom → specialty mapping with weights and follow-up questions |
| **doctors**            | Doctor profiles (name, image, active status)                   |
| **doctor_specialties** | Doctor ↔ specialty links (many-to-many)                        |
| **doctor_availability**| Weekly schedule templates (day, start/end time, slot duration)  |
| **doctor_blocks**      | One-off unavailability periods (conferences, time off)         |
| **patients**           | Patient records identified by 9-digit UIN                      |
| **appointments**       | Booked appointments with triage data, severity, and follow-up links |
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

The triage loop runs up to 5 times. If no specialty is determined after 5 rounds, the system falls back to the patient's stated preference or lists all specialties for manual selection.

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

Prompt/tool alignment note: if the live assistant still self-validates UIN length or invents `INVALID` reasons after you update this repo, refresh the system prompt in the Vapi dashboard so the hosted assistant matches the checked-in prompt.

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
    "answers": {
      "type": "object",
      "description": "Answers to follow-up triage questions from a previous triage call (optional)"
    }
  },
  "required": ["symptoms"]
}
```

### list_specialties

List all available medical specialties. Used as a fallback when triage cannot determine a specialty.

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
    "severity_description": {
      "type": "string",
      "description": "Description of symptom severity (optional)"
    },
    "severity_rating": {
      "type": "number",
      "description": "Numeric severity rating 1-10 (optional)"
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
