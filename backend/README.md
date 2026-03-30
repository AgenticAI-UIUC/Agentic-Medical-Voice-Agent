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
2. **Check for follow-up** — If this is a follow-up, find the original appointment and skip to scheduling with the same doctor.
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

| Method | Path                                     | Purpose                                                |
| ------ | ---------------------------------------- | ------------------------------------------------------ |
| POST   | `/api/v1/vapi/tools/identify-patient`    | Look up patient by UIN                                 |
| POST   | `/api/v1/vapi/tools/register-patient`    | Register new patient, returns 9-digit UIN              |
| POST   | `/api/v1/vapi/tools/triage`              | Symptoms → specialty matching with follow-up questions |
| POST   | `/api/v1/vapi/tools/list-specialties`    | List all specialties (fallback if triage can't match)  |
| POST   | `/api/v1/vapi/tools/find-slots`          | Find available times by specialty or specific doctor   |
| POST   | `/api/v1/vapi/tools/book`                | Book an appointment                                    |
| POST   | `/api/v1/vapi/tools/find-appointment`    | Find a patient's existing appointment                  |
| POST   | `/api/v1/vapi/tools/reschedule`          | Find replacement slots for an existing appointment     |
| POST   | `/api/v1/vapi/tools/reschedule-finalize` | Finalize a reschedule after slot selection             |
| POST   | `/api/v1/vapi/tools/cancel`              | Cancel an appointment                                  |

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

### 6. Vapi tools configurations

**Name**
reschedule_finalize

**Description**
Finalizes a reschedule by atomically booking the new slot and cancelling the original appointment. Call this after the patient picks a new slot from the reschedule tool results.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "end_at": {
      "description": "ISO 8601 end time of the new slot",
      "type": "string"
    },
    "reason": {
      "description": "Reason for visit, carried over from the original appointment",
      "type": "string"
    },
    "start_at": {
      "description": "ISO 8601 start time of the new slot",
      "type": "string"
    },
    "doctor_id": {
      "description": "The doctor ID for the new slot",
      "type": "string"
    },
    "patient_id": {
      "description": "The patient's ID",
      "type": "string"
    },
    "specialty_id": {
      "description": "Specialty ID, carried over from the original appointment",
      "type": "string"
    },
    "original_appointment_id": {
      "description": "The ID of the appointment being rescheduled",
      "type": "string"
    }
  },
  "required": [
    "original_appointment_id",
    "patient_id",
    "doctor_id",
    "start_at",
    "end_at"
  ]
}
```

**Server URL (local dev)**

https://tracklessly-instinctive-gertude.ngrok-free.dev/api/v1/vapi/tools/reschedule-finalize

**Name**
cancel

**Description**
Cancel an existing confirmed appointment. Sets the appointment status to CANCELLED, which frees the time slot for other patients.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "appointment_id": {
      "description": "UUID of the appointment to cancel (from find_appointment)",
      "type": "string"
    }
  },
  "required": ["appointment_id"]
}
```

**Server URL (local dev)**

https://tracklessly-instinctive-gertude.ngrok-free.dev/api/v1/vapi/tools/cancel

**Name**

reschedule

**Description**

Find new available slots for rescheduling an existing appointment. Looks up the original appointment's specialty and finds slots for the same specialty. Does not cancel the old appointment — that happens when the new one is booked.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "end_at": {
      "description": "Fallback ISO 8601 end time from the selected slot. Only use if slot_number is unavailable.",
      "type": "string"
    },
    "reason": {
      "description": "Reason for the appointment if available",
      "type": "string"
    },
    "start_at": {
      "description": "Fallback ISO 8601 start time from the selected slot. Only use if slot_number is unavailable.",
      "type": "string"
    },
    "doctor_id": {
      "description": "Fallback doctor UUID from the selected slot. Only use if slot_number is unavailable.",
      "type": "string"
    },
    "patient_id": {
      "description": "The patient UUID",
      "type": "string"
    },
    "slot_number": {
      "description": "The slot_number of the chosen option from the most recent reschedule response. Pass this to finalize the reschedule instead of passing doctor_id, start_at, end_at manually.",
      "type": "integer"
    },
    "specialty_id": {
      "description": "Specialty UUID if available",
      "type": "string"
    },
    "preferred_day": {
      "description": "Preferred day such as next week, Monday, or tomorrow",
      "type": "string"
    },
    "appointment_id": {
      "description": "The ID of the appointment to reschedule",
      "type": "string"
    },
    "preferred_time": {
      "description": "Preferred time of day such as morning, afternoon, or any",
      "type": "string"
    }
  },
  "required": ["appointment_id"]
}
```

**Server URL (local dev)**
https://tracklessly-instinctive-gertude.ngrok-free.dev/api/v1/vapi/tools/reschedule

**Name**

find_appointment

**Description**

Find a patient's existing confirmed appointment for rescheduling or cancellation. Can narrow down by doctor name and/or reason. Returns the matched appointment or a list if multiple match.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "reason": {
      "description": "Original reason or symptoms (partial match)",
      "type": "string"
    },
    "patient_id": {
      "description": "UUID of the patient",
      "type": "string"
    },
    "doctor_name": {
      "description": "Name of the doctor (partial match, case-insensitive)",
      "type": "string"
    }
  },
  "required": ["patient_id"]
}
```

**Server URL (local dev)**

https://tracklessly-instinctive-gertude.ngrok-free.dev/api/v1/vapi/tools/find-appointment

**Name**

book

**Description**

Book a confirmed appointment for a patient with a specific doctor at a specific time. Includes clinical info collected during triage. Prevents double-booking via a database constraint.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "end_at": {
      "description": "Fallback ISO 8601 end time from the selected slot. Only use if slot_number is unavailable.",
      "type": "string"
    },
    "reason": {
      "description": "Brief reason for the visit",
      "type": "string"
    },
    "urgency": {
      "description": "Urgency level. Default ROUTINE.",
      "type": "string",
      "enum": ["ROUTINE", "URGENT"]
    },
    "start_at": {
      "description": "Fallback ISO 8601 start time from the selected slot. Only use if slot_number is unavailable.",
      "type": "string"
    },
    "symptoms": {
      "description": "Patient-described symptoms",
      "type": "string"
    },
    "doctor_id": {
      "description": "Fallback doctor UUID from the selected slot. Only use if slot_number is unavailable.",
      "type": "string"
    },
    "patient_id": {
      "description": "The patient UUID",
      "type": "string"
    },
    "slot_number": {
      "description": "The slot_number of the chosen option from the most recent find_slots response. Pass this instead of doctor_id, start_at, end_at.",
      "type": "integer"
    },
    "specialty_id": {
      "description": "Specialty UUID",
      "type": "string"
    },
    "severity_rating": {
      "description": "Patient self-rated severity 1-10",
      "type": "integer"
    },
    "follow_up_from_id": {
      "description": "Appointment UUID of the original visit, only if this is a confirmed follow-up",
      "type": "string"
    },
    "severity_description": {
      "description": "Patient description of how bad the symptoms feel",
      "type": "string"
    }
  },
  "required": ["patient_id"]
}
```

**Server URL (local dev)**

https://tracklessly-instinctive-gertude.ngrok-free.dev/api/v1/vapi/tools/book

**Name**

find_slots

**Description**

Search for available appointment slots. Can search by specialty (finds slots across all doctors in that specialty) or by a specific doctor (for follow-ups). Supports natural language day and time preferences.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "doctor_id": {
      "description": "UUID of a specific doctor. Use for follow-ups with the same doctor.",
      "type": "string"
    },
    "specialty_id": {
      "description": "UUID of the specialty. Required if doctor_id is not provided.",
      "type": "string"
    },
    "preferred_day": {
      "description": "Natural language day preference (e.g. \"next Monday\", \"this week\", \"tomorrow\", \"2 weeks\")",
      "type": "string"
    },
    "preferred_time": {
      "description": "Time-of-day preference: \"morning\", \"afternoon\", or \"any\"",
      "type": "string"
    }
  },
  "required": []
}
```

**Server URL (local dev)**

https://tracklessly-instinctive-gertude.ngrok-free.dev/api/v1/vapi/tools/find-slots

**Name**

list_specialties

**Description**

Return all available medical specialties. Use as a fallback when triage cannot determine a specialty after multiple rounds, so the patient can choose manually.

**Parameters**

```json
{
  "type": "object",
  "properties": {},
  "required": []
}
```

**Server URL (local dev)**

https://tracklessly-instinctive-gertude.ngrok-free.dev/api/v1/vapi/tools/list-specialties

**Name**

triage

**Description**

Analyze patient symptoms to determine the appropriate medical specialty. Returns either a matched specialty (if confidence is high enough) or follow-up questions to narrow down the diagnosis. Supports iterative calls — pass previous answers back in to refine the match.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "answers": {
      "description": "Key-value pairs of previously answered follow-up questions",
      "type": "object",
      "properties": {}
    },
    "symptoms": {
      "description": "Comma-separated symptom keywords (e.g. \"chest pain, shortness of breath\")",
      "type": "string"
    }
  },
  "required": ["symptoms"]
}
```

**Server URL (local dev)**

https://tracklessly-instinctive-gertude.ngrok-free.dev/api/v1/vapi/tools/triage

**Name**

register_patient

**Description**

Register a new patient in the system using their university UIN, full name, and phone number. Checks for duplicate UIN and phone before creating the record.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "uin": {
      "description": "The patient's 9-digit university-issued UIN",
      "type": "string"
    },
    "email": {
      "description": "Patient's email address",
      "type": "string"
    },
    "phone": {
      "description": "Patient's phone number (10+ digits)",
      "type": "string"
    },
    "allergies": {
      "description": "Known allergies",
      "type": "string"
    },
    "full_name": {
      "description": "Patient's full name",
      "type": "string"
    }
  },
  "required": ["uin", "full_name", "phone"]
}
```

**Server URL (local dev)**

https://tracklessly-instinctive-gertude.ngrok-free.dev/api/v1/vapi/tools/register-patient

**Name**

identify_patient

**Description**

Look up an existing patient by their 9-digit university UIN. Returns the patient record if found, or an error if the UIN is invalid or not registered.

**Parameters**

```json
{
  "type": "object",
  "properties": {
    "uin": {
      "description": "The patient's 9-digit university-issued UIN",
      "type": "string"
    }
  },
  "required": ["uin"]
}
```

**Server URL (local dev)**
https://tracklessly-instinctive-gertude.ngrok-free.dev/api/v1/vapi/tools/identify-patient
