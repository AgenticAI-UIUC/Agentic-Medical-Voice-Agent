# Medical Voice Agent — Backend

A FastAPI backend for a voice-based medical appointment scheduler powered by [Vapi.ai](https://vapi.ai) and [Supabase](https://supabase.com).

The system handles patient identification, symptom triage with iterative specialty matching, appointment booking, rescheduling, and cancellation — all through voice conversation.

## Architecture

```
Patient calls → Vapi voice agent → Vapi tool calls → This backend → Supabase
```

Vapi manages the voice conversation and LLM orchestration. When the agent needs to take an action (look up a patient, find available slots, book an appointment), it calls one of the tool endpoints exposed by this backend. The backend computes results against Supabase and returns structured responses that the voice agent reads back to the patient.

There are no pre-generated appointment slots. Available times are computed on the fly from doctor availability templates, minus existing appointments and one-off blocks. This eliminates the need for any cron jobs or slot generation scripts.

## Conversation flow

1. **Identify patient** — Ask if new or returning. New patients are registered with a 9-digit UIN. Returning patients provide their UIN for lookup.
2. **Check for follow-up** — If this is a follow-up, find the original appointment, including past completed visits when needed, and skip to scheduling with the same doctor.
3. **Triage** — Collect symptoms, query the symptom-specialty mapping table, and iteratively narrow down the right specialty (up to 5 rounds of follow-up questions). Patient can override.
4. **Find slots** — Compute available appointment times for doctors of the matched specialty within the patient's preferred time window.
5. **Book** — Confirm and insert the appointment. A unique constraint on `(doctor_id, start_at)` prevents double-booking at the database level.
6. **Reschedule / Cancel** — Patient identifies an existing appointment by doctor name, date, or reason. Rescheduling cancels the old appointment and finds new slots for the same specialty.

## Project structure

```
backend/
├── app/
│   ├── main.py                          # FastAPI app, CORS, lifespan
│   ├── config.py                        # Settings (Supabase, timezone, etc.)
│   ├── supabase.py                      # Supabase client singleton
│   ├── api/
│   │   ├── vapi_helpers.py              # Parse Vapi tool-call envelopes
│   │   ├── vapi_webhook.py              # POST /vapi/events (end-of-call transcript saving)
│   │   ├── vapi_tools/
│   │   │   ├── identify_patient.py      # Lookup / register patient by UIN
│   │   │   ├── triage.py               # Symptom → specialty matching loop
│   │   │   ├── find_slots.py           # Compute available appointment times
│   │   │   ├── book.py                 # Book an appointment
│   │   │   ├── reschedule.py           # Find existing appointment + rebook
│   │   │   └── cancel.py              # Cancel an appointment
│   │   └── admin/
│   │       └── routes.py               # Doctor/patient/appointment CRUD (no auth yet)
│   └── services/
│       ├── slot_engine.py              # Compute slots from availability - bookings - blocks
│       ├── triage_engine.py            # Query symptom DB, score specialties
│       └── time_utils.py              # Timezone handling, NLP date parsing, voice formatting
├── schema.sql                          # Supabase database schema
├── pyproject.toml
├── .env.example
└── README.md
```

## API endpoints

### Vapi tool endpoints

All Vapi tool endpoints accept the standard Vapi tool-call payload and return `{"results": [...]}`.

| Method | Path                                  | Purpose                                                |
| ------ | ------------------------------------- | ------------------------------------------------------ |
| POST   | `/api/v1/vapi/tools/identify-patient` | Look up patient by UIN                                 |
| POST   | `/api/v1/vapi/tools/register-patient` | Register new patient, returns 9-digit UIN              |
| POST   | `/api/v1/vapi/tools/triage`           | Symptoms → specialty matching with follow-up questions |
| POST   | `/api/v1/vapi/tools/list-specialties` | List all specialties (fallback if triage can't match)  |
| POST   | `/api/v1/vapi/tools/find-slots`       | Find available times by specialty or specific doctor   |
| POST   | `/api/v1/vapi/tools/book`             | Book an appointment                                    |
| POST   | `/api/v1/vapi/tools/find-appointment` | Find a patient's existing appointment                  |
| POST   | `/api/v1/vapi/tools/reschedule`       | Cancel old + find new slots for same specialty         |
| POST   | `/api/v1/vapi/tools/cancel`           | Cancel an appointment                                  |

### Vapi webhook

| Method | Path                  | Purpose                                                      |
| ------ | --------------------- | ------------------------------------------------------------ |
| POST   | `/api/v1/vapi/events` | Receives Vapi status events; saves transcript on end-of-call |

### Admin endpoints (no auth)

| Method | Path                                     | Purpose                                       |
| ------ | ---------------------------------------- | --------------------------------------------- |
| GET    | `/api/v1/admin/doctors`                  | List doctors                                  |
| POST   | `/api/v1/admin/doctors`                  | Create doctor with specialties + availability |
| GET    | `/api/v1/admin/doctors/:id/availability` | Get weekly availability                       |
| PUT    | `/api/v1/admin/doctors/:id/availability` | Replace weekly availability                   |
| POST   | `/api/v1/admin/doctors/:id/blocks`       | Add time-off block                            |
| GET    | `/api/v1/admin/doctors/:id/blocks`       | List blocks                                   |
| DELETE | `/api/v1/admin/doctors/:id/blocks/:bid`  | Remove a block                                |
| GET    | `/api/v1/admin/patients`                 | List patients                                 |
| GET    | `/api/v1/admin/patients/:uin`            | Get patient by UIN                            |
| GET    | `/api/v1/admin/appointments`             | List appointments (filterable by status)      |
| GET    | `/health`                                | Health check                                  |

## Setup

### 1. Database

Create a new Supabase project, then run `schema.sql` in the SQL editor. This creates 9 tables:

- `specialties` — medical specialties lookup
- `symptom_specialty_map` — symptom → specialty mapping with weights and follow-up questions
- `doctors` — doctor profiles
- `doctor_specialties` — doctor ↔ specialty links
- `doctor_availability` — weekly schedule templates (breaks = separate rows)
- `doctor_blocks` — one-off unavailability (sick days, meetings)
- `patients` — patient records with 9-digit UIN
- `appointments` — booked appointments with triage data
- `conversations` — call transcripts from Vapi

### 2. Environment

```bash
cp .env.example .env
# Fill in your Supabase URL and service role key
```

### 3. Install and run

```bash
# Using uv (recommended)
uv sync
uv run uvicorn app.main:app --reload




# Or with pip
pip install -e .
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`. OpenAPI docs at `http://localhost:8000/api/v1/openapi.json` (local environment only).

### 4. Seed data

Create a doctor with availability using the admin endpoint:

```bash
curl -X POST http://localhost:8000/api/v1/admin/doctors \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Dr. Sarah Chen",
    "specialties": ["General Practice", "Internal Medicine"],
    "availability": [
      {"day_of_week": 1, "start_time": "09:00", "end_time": "12:00"},
      {"day_of_week": 1, "start_time": "13:00", "end_time": "17:00"},
      {"day_of_week": 2, "start_time": "09:00", "end_time": "12:00"},
      {"day_of_week": 2, "start_time": "13:00", "end_time": "17:00"},
      {"day_of_week": 3, "start_time": "09:00", "end_time": "12:00"},
      {"day_of_week": 3, "start_time": "13:00", "end_time": "17:00"},
      {"day_of_week": 4, "start_time": "09:00", "end_time": "12:00"},
      {"day_of_week": 4, "start_time": "13:00", "end_time": "17:00"},
      {"day_of_week": 5, "start_time": "09:00", "end_time": "12:00"},
      {"day_of_week": 5, "start_time": "13:00", "end_time": "17:00"}
    ]
  }'
```

Note: `day_of_week` uses Sun=0 through Sat=6. The two rows per day (9–12, 1–5) model the lunch break as a gap.

Populate `symptom_specialty_map` in the Supabase dashboard or via SQL inserts to enable the triage flow.

### 5. Connect Vapi

In your Vapi assistant configuration, add each tool endpoint as a server tool pointing to your deployed backend URL (e.g. `https://your-domain.com/api/v1/vapi/tools/identify-patient`).

Set the server URL for the events webhook to `https://your-domain.com/api/v1/vapi/events`.

## Design decisions

**Computed slots, not pre-generated.** Available times are calculated on the fly from `doctor_availability` minus booked `appointments` and `doctor_blocks`. No cron jobs, no stale slot data.

**Breaks as separate availability rows.** Instead of `break_start`/`break_end` columns, a doctor's lunch break is modeled as two availability windows (9–12 and 1–5). Simpler schema, simpler slot engine.

**9-digit UIN as patient identifier.** Patients speak this over the phone. It's separate from the internal UUID primary key — easy to say, easy to confirm.

**One booking flow.** Every appointment goes through the same path: find slots → book. Rescheduling is cancel + find + book. No competing code paths.

**Thin routes, service layer.** Vapi tool endpoints just parse the payload and delegate to `services/`. Business logic lives in `slot_engine.py` and `triage_engine.py`.

**No auth yet.** Admin endpoints are unprotected. Add Supabase Auth or JWT middleware when ready.
