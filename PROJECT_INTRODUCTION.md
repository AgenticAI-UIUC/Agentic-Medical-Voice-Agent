# Agentic Medical Voice Agent - Project Introduction

## 1. What this project is

`Agentic Medical Voice Agent` is a full-stack medical scheduling system designed around a phone-based AI assistant.

The core idea is simple:

1. A patient calls the clinic.
2. A Vapi-powered voice assistant handles the conversation.
3. The assistant calls backend tools to identify the patient, triage symptoms, find appointment slots, and book, reschedule, or cancel visits.
4. The backend persists clinic data in Supabase/PostgreSQL.
5. A Next.js web app provides a staff-facing dashboard for browsing doctors and managing account-oriented workflows.

This repo is not just a chatbot demo. It is a workflow-oriented scheduling system with:

- patient identification based on a spoken 9-digit UIN
- symptom-driven specialty matching
- on-demand slot computation from real availability templates
- transactional rescheduling logic
- transcript capture from voice calls

At a high level, the project sits at the intersection of:

- conversational AI
- healthcare workflow automation
- scheduling systems
- full-stack web tooling

## 2. What problem it solves

The repo aims to automate common front-desk tasks for a university or clinic setting:

- booking new appointments
- handling first-time patient registration
- routing patients to the right specialty based on symptoms
- rescheduling existing appointments without creating inconsistent state
- cancelling appointments cleanly
- preserving call context and transcripts for later review

Instead of asking patients to navigate menus or wait on a human scheduler, the system tries to guide them through a natural conversation.

## 3. Product experience in one paragraph

The intended patient experience is: call the clinic, state what you need, confirm identity or complete first-time registration as part of that same request, describe symptoms, get routed to an appropriate specialty unless the symptoms look emergent, hear a few appointment options in natural language, confirm a slot, and finish the call with a transcript saved to the database. For existing appointments, the same voice assistant can locate a booked visit and either cancel it or swap it for a new slot.

## 4. Core flows the repo is built around

### New appointment flow

1. Determine whether the caller is new or returning.
2. Register or identify the patient using a 9-digit UIN while preserving the caller's original booking intent. If they are truly new and were just registered, continue straight into symptom collection rather than asking about follow-up care.
3. Collect symptoms and severity.
4. Run triage to determine a specialty.
5. Ask for scheduling preferences such as preferred day and morning vs afternoon.
6. Compute live availability.
7. Book the appointment.
8. Save the conversation transcript when the call ends.

### Reschedule flow

1. Identify the patient.
2. Find the existing upcoming appointment.
3. Ask for a new preferred day and time window.
4. Find alternative slots.
5. Finalize the swap using a database transaction so the new booking and old cancellation happen together.

### Cancel flow

1. Identify the patient.
2. Find the appointment.
3. Confirm cancellation intent.
4. Mark the appointment as cancelled.

## 5. End-to-end architecture

```text
Patient phone call
  -> Vapi voice assistant
  -> FastAPI backend tool endpoints
  -> Supabase / PostgreSQL
  -> Next.js dashboard for staff-facing views
```

More concretely:

- `Vapi` handles speech, LLM orchestration, and tool-calling behavior.
- `FastAPI` exposes tool endpoints under `/api/v1/vapi/tools/*`.
- `Supabase` stores patients, doctors, specialties, availability, appointments, and conversations.
- `Next.js` consumes backend APIs for dashboard-style experiences.

## 6. Main technologies in the repo

### Backend

- Python 3.11+
- FastAPI
- Pydantic / `pydantic-settings`
- Supabase Python client
- Uvicorn

### Frontend

- Next.js 16 App Router
- React 19
- TypeScript
- Tailwind CSS v4
- shadcn/ui
- TanStack Query
- React Hook Form
- Zod

### Data and infrastructure

- Supabase
- PostgreSQL
- Vapi.ai

### Tooling

- `uv` for Python dependency and environment management
- `pnpm` for frontend package management
- ESLint for frontend linting
- Pytest for backend tests

## 7. Repo layout

```text
Agentic-Medical-Voice-Agent/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── admin/
│   │   │   ├── vapi_tools/
│   │   │   ├── vapi_helpers.py
│   │   │   └── vapi_webhook.py
│   │   ├── services/
│   │   ├── config.py
│   │   ├── main.py
│   │   └── supabase.py
│   ├── migrations/
│   ├── schema.sql
│   ├── seed.sql
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── hooks/
│   │   └── lib/
│   ├── README.md
│   └── package.json
├── workflow/
│   ├── identification_registration_subflow.svg
│   ├── triage_booking_subflow.svg
│   └── voice_agent_main_flow.svg
├── Medical Voice Agent — System Prompt.md
├── README.md
└── CLAUDE.md
```

## 8. Backend structure and responsibilities

The backend is the operational core of the project. It owns validation, slot computation, appointment mutation logic, and transcript persistence.

### `backend/app/main.py`

This is the FastAPI entry point. It:

- creates the application object
- enables CORS
- mounts routers under `/api/v1`
- exposes `/health`

In local mode, OpenAPI is enabled. In non-local environments it is hidden by default.

### `backend/app/config.py`

Central runtime settings include:

- `PROJECT_NAME`
- `ENVIRONMENT`
- `API_V1_STR`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `CLINIC_TIMEZONE`
- `SCHEDULING_HORIZON_DAYS`
- `VAPI_WEBHOOK_SECRET`
- `FRONTEND_HOST`

The clinic timezone defaults to `America/Chicago`, and scheduling currently defaults to a 14-day horizon.

### `backend/app/supabase.py`

Provides a lazily initialized singleton Supabase client configured with:

- `auto_refresh_token=False`
- `persist_session=False`

This backend uses the service role key and acts as a trusted server-side integration layer.

## 9. Vapi tool endpoints

The Vapi-facing endpoints live under:

`/api/v1/vapi/tools`

They all follow the same pattern:

- read the Vapi tool-call envelope
- extract arguments
- delegate to a handler
- return Vapi-compatible tool results as `{"results": [...]}`

### `identify_patient.py`

Implements:

- `/identify-patient`
- `/register-patient`

Key behavior:

- normalizes spoken digits like `"one two three"` into numeric UIN text
- strips punctuation from phone numbers
- looks up patients by UIN
- registers new patients with validation
- prevents duplicate UINs while allowing shared phone numbers

This is important because the voice layer is intentionally told not to perform its own strict validation logic.

### `triage.py`

Implements:

- `/triage`
- `/list-specialties`

Key behavior:

- accepts symptoms and optional follow-up answers
- asks the triage engine to classify or narrow down specialty matches
- returns emergency advice immediately when needed
- falls back to listing all specialties when triage cannot confidently decide

### `find_slots.py`

Implements:

- `/find-slots`

Key behavior:

- can search by `specialty_id` or by `doctor_id`
- supports natural scheduling preferences such as day phrases and time buckets
- returns human-readable labels for voice playback

### `book.py`

Implements:

- `/book`

Key behavior:

- validates required booking data
- validates ISO datetime inputs
- confirms the chosen slot is real and currently bookable
- inserts a confirmed appointment
- attaches the Vapi call id when available

### `reschedule.py`

Implements:

- `/find-appointment`
- `/reschedule`
- `/reschedule-finalize`

This file is one of the most important pieces in the repo because it covers the multi-step logic for modifying an existing appointment.

Key behavior:

- finds upcoming appointments for a patient
- narrows candidates by doctor name or reason
- searches for replacement slots
- finalizes the reschedule using a database RPC called `reschedule_appointment`

The finalization step is designed to avoid partial failure by creating the new appointment and cancelling the old appointment together.

### `cancel.py`

Implements:

- `/cancel`

Key behavior:

- validates appointment ids
- ensures the appointment exists and is still active
- updates status to `CANCELLED`

### `vapi_webhook.py`

Implements:

- `/api/v1/vapi/events`

Key behavior:

- optionally verifies a Vapi secret header
- listens for end-of-call events
- saves transcripts and summaries to `conversations`
- links the conversation back to the related appointment when possible

## 10. Backend service layer

The project follows a "thin route, real service layer" style for its most interesting logic.

### `services/triage_engine.py`

This module contains two major ideas:

1. Emergency red-flag detection
2. Weighted specialty matching

#### Emergency detection

The emergency classifier uses regex patterns to catch high-risk phrases related to:

- cardiac emergencies
- stroke symptoms
- breathing emergencies
- severe bleeding or trauma
- loss of consciousness
- anaphylaxis
- suicidal or crisis language
- poisoning

If a symptom string hits one of these patterns, the scheduling flow should stop and the caller should be instructed to seek urgent help instead of booking a normal appointment.

The mental health crisis path is handled separately and returns a `988`-oriented message rather than a generic `911`-only message.

#### Specialty matching

If the case is not emergent, the engine:

- queries `symptom_specialty_map`
- sums specialty weights for matching symptoms
- boosts or penalizes candidate specialties based on follow-up answers
- normalizes scores into confidence values
- returns either:
  - a confident specialty recommendation, or
  - follow-up questions for the next round

By default, confidence must be at least `0.6` to consider the specialty determined.

### `services/slot_engine.py`

This is the scheduling engine.

Its job is to compute bookable appointment slots from first principles instead of reading from a pre-generated slot table.

The logic combines:

- weekly doctor availability templates
- currently booked appointments
- one-off doctor blocks
- horizon limits
- morning / afternoon filtering
- natural language date ranges

Important design detail:

- there is no cron job generating slots ahead of time
- slots are computed when requested

This reduces stale data risk and makes schedule changes immediately visible.

The same module also exposes `validate_slot`, which checks:

- the slot is in the future
- the slot is inside the scheduling horizon
- the doctor exists and is active
- the requested time fits a real availability window
- the slot is not blocked
- the slot is not already booked

### `services/time_utils.py`

This module converts conversational scheduling language into concrete search windows.

Examples it can understand include:

- `today`
- `tomorrow`
- `this week`
- `next week`
- `weekend`
- weekday names such as `monday`
- phrases such as `next monday`
- calendar dates such as `2/24`
- month/day phrases such as `feb 24`
- ranges like `2 weeks`

It also formats UTC datetimes into clinic-local, voice-friendly labels such as:

`Monday, March 31 at 2 PM`

## 11. Database model

The database schema is centered on appointments and the metadata needed to decide who should be seen, by whom, and when.

### Core tables

#### `specialties`

Lookup table for medical specialties such as:

- General Practice
- Cardiology
- Dermatology
- Neurology
- Psychiatry

#### `symptom_specialty_map`

Maps symptom strings to specialties with:

- a numeric `weight`
- optional `follow_up_questions`

This table is what powers the rule-based triage engine.

#### `doctors`

Stores doctor identity and activity status.

#### `doctor_specialties`

Many-to-many join between doctors and specialties.

#### `doctor_availability`

Stores recurring weekly schedule templates using:

- `day_of_week`
- `start_time`
- `end_time`
- `slot_minutes`
- `timezone`

Lunch breaks or gaps are represented as separate rows rather than a special "break" column model.

#### `doctor_blocks`

Represents one-off unavailability such as:

- conferences
- personal appointments
- time off

#### `patients`

Stores patient records with:

- internal UUID primary key
- 9-digit unique UIN
- phone number (shared numbers allowed)
- name
- optional email
- optional allergies

#### `appointments`

This is the most important transactional table.

It stores:

- patient and doctor references
- optional specialty
- optional conversation link
- follow-up relationship to a prior appointment
- start and end timestamps
- reason and symptoms
- severity information
- urgency
- status
- Vapi call id

Supported statuses in schema:

- `CONFIRMED`
- `CANCELLED`
- `COMPLETED`
- `NO_SHOW`

#### `conversations`

Stores:

- Vapi `call_id`
- transcript JSON
- summary text
- optional `patient_id`

This gives the system a durable record of what happened during a call.

## 12. Database constraints and migrations

The repo shows a clear evolution toward stronger booking integrity.

### `001_reschedule_appointment_fn.sql`

Introduces the `reschedule_appointment` Postgres function for atomic rescheduling.

### `002_unique_doctor_appointment.sql`

Adds a partial unique index preventing two `CONFIRMED` appointments for the same doctor at the same `start_at`.

### `003_reschedule_verify_patient.sql`

Hardens the reschedule RPC by verifying the original appointment belongs to the patient performing the request.

### Current working-tree change: `004_exclusion_overlap_constraint.sql`

In this checkout, there is also an uncommitted migration that upgrades overlap protection further:

- it drops the weaker same-start unique index
- it adds a GiST exclusion constraint
- it prevents overlapping `CONFIRMED` appointments for the same doctor across time ranges

This is a meaningful improvement because exact start-time uniqueness is not enough to prevent all overlapping bookings.

## 13. Seed data

`backend/seed.sql` makes the repo easier to demo and test.

It currently seeds:

- 10 specialties
- about 50 symptom-to-specialty mappings
- 8 doctors
- doctor-specialty associations
- weekly availability templates
- a small number of doctor blocks
- 5 test patients with spoken UINs
- sample appointments, including upcoming and completed ones

This makes the repo especially useful for local demos and voice-flow testing.

## 14. Frontend structure and current role

The frontend is a Next.js application that appears to serve as a staff portal.

### Current visible pages

From the source currently present in this checkout:

- `/login` for staff sign-in
- `/` for browsing active doctors
- `/doctors/[doctorId]` for a schedule-style weekly doctor view
- `/users` for admin user management
- `/settings` for profile and password changes

### Notable frontend characteristics

- client-side token storage
- TanStack Query for data access
- typed API wrappers in `frontend/src/lib/api`
- shadcn/ui-based component library
- light/dark theme support

### What the UI appears to be optimized for

The visible frontend focuses more on staff operations than patient self-service. It looks like a dashboard for clinic personnel rather than a public scheduling interface.

## 15. Important repo reality check: backend/frontend alignment

One of the most useful things for a new engineer to know is that the repo currently looks slightly mid-transition.

### What is clearly implemented in visible backend source

- Vapi tool endpoints under `/api/v1/vapi/tools/*`
- transcript webhook handling
- admin routes under `/api/v1/admin/*`
- core triage and slot services

### What the frontend expects

The frontend currently calls additional endpoints such as:

- `/api/v1/login/access-token`
- `/api/v1/users/*`
- `/api/v1/doctors`
- `/api/v1/doctors/{id}/schedule`

### What is unusual in this checkout

- source files for those auth and user routes are not present in normal Python source form
- there are stale `__pycache__` artifacts that suggest some of those modules existed earlier
- `backend/.env.example` also includes auth-style variables such as `SECRET_KEY` and `ACCESS_TOKEN_EXPIRE_MINUTES` that are not used by the current visible `Settings` model

The practical takeaway is:

- the voice-agent backend is the most complete and coherent part of the repo
- the staff dashboard and auth system may be ahead of, behind, or partially detached from the currently visible backend source

That does not make the repo inconsistent overall, but it does mean a new contributor should verify actual runnable API coverage before assuming the frontend and backend are fully synchronized.

## 16. Voice agent behavior and prompt design

The file `Medical Voice Agent — System Prompt.md` is a major part of the project, not just documentation.

It defines:

- assistant persona
- how to route callers into booking, rescheduling, or cancelling
- when to register vs identify
- how to read back UINs and phone numbers
- how to handle triage loops
- when to stop and advise emergency escalation
- how to present slot options
- how to use `reschedule_finalize` correctly

In other words, this repo's behavior is split between:

- deterministic backend code
- prompt-level orchestration rules for the voice assistant

That combination is central to how the system works.

## 17. Workflow diagrams and supporting docs

The `workflow/` directory contains visual diagrams for:

- patient identification and registration
- triage and booking
- the main voice agent flow

These are useful onboarding artifacts because they explain conversation structure at a glance, while the code explains the actual execution details.

The repo also contains:

- `README.md` for the top-level introduction, API reference, backend setup notes, and database guidance
- `frontend/README.md` for dashboard structure
- `CLAUDE.md` with contributor-oriented engineering notes

## 18. Testing posture

The visible backend test coverage is currently focused and limited rather than broad.

The included test file:

- `backend/tests/test_emergency_classifier.py`

This test suite validates the regex-based emergency classifier and checks:

- emergencies are detected for known red-flag phrases
- mental health crises return the `988` guidance path
- general emergencies return `911` / ER guidance
- ordinary symptoms do not trigger false emergency classification

This gives confidence in one safety-critical area, but it also suggests there is room to expand automated coverage for:

- booking validation
- slot generation
- reschedule edge cases
- webhook persistence

## 19. Local development workflow

### Backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

Optional tests:

```bash
uv run pytest
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

### Database

Use Supabase with:

- `backend/schema.sql` as the current schema reference
- `backend/seed.sql` for demo and test data
- migration files in `backend/migrations/` for incremental database changes

One caveat: the header of `backend/schema.sql` says it is "for context only," so treat the schema file and the migrations together as the source of truth rather than assuming the schema snapshot is a perfect one-shot bootstrap artifact.

### Vapi

Point Vapi server tools at your deployed or tunneled backend URLs under:

- `/api/v1/vapi/tools/*`
- `/api/v1/vapi/events`

## 20. Environment variables worth knowing first

### Backend

From `.env.example`, the key values are:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `CLINIC_TIMEZONE`
- `SCHEDULING_HORIZON_DAYS`
- `VAPI_WEBHOOK_SECRET`
- `FRONTEND_HOST`

There are also extra variables in the example file that appear related to auth and extended CORS setup:

- `BACKEND_CORS_ORIGINS`
- `SECRET_KEY`
- `ACCESS_TOKEN_EXPIRE_MINUTES`

### Frontend

From `frontend/.env.local.example`:

- `NEXT_PUBLIC_API_BASE_URL`

## 21. Design choices that define the project

Several engineering choices give this repo its identity:

### 1. Slot computation is stateless

The system does not store a giant table of pre-generated appointment slots. It derives availability from recurring schedules plus real-time conflicts.

### 2. The backend owns validation

The voice assistant is not trusted to validate digit counts, phone formats, or slot legitimacy. The backend performs validation and returns clear messages for the assistant to relay.

### 3. Triage is rule-driven and explainable

The current triage model is not a black-box classifier. It is a weighted rules system backed by a database table of symptom mappings and follow-up prompts.

### 4. Safety is baked into the flow

Emergency red-flag detection is evaluated before routine specialty matching.

### 5. Rescheduling is treated as a transactional problem

The repo correctly avoids implementing rescheduling as "cancel first, hope book succeeds later."

### 6. Timezone clarity matters

The system stores UTC but speaks in clinic-local time, which is exactly the right split for scheduling software.

## 22. Who this repo is good for

This codebase is especially interesting for people building:

- voice agents that take real actions
- scheduling systems with human-friendly date language
- healthcare-adjacent workflow automation
- FastAPI and Next.js full-stack apps backed by Supabase
- systems that combine prompt orchestration with deterministic business logic

## 23. What a new contributor should read first

If you are onboarding to this repo, a good reading order is:

1. `README.md`
2. `backend/app/main.py`
3. `backend/app/api/vapi_tools/*`
4. `backend/app/services/triage_engine.py`
5. `backend/app/services/slot_engine.py`
6. `backend/schema.sql`
7. `Medical Voice Agent — System Prompt.md`
8. `frontend/src/app/page.tsx`
9. `frontend/src/lib/api/*`

That path gives a fast understanding of both the product and the actual control flow.

## 24. Best concise summary

This repository is a medically oriented voice scheduling platform centered on Vapi tool calls and a FastAPI backend. Its strongest, most complete story is the patient voice workflow: identify or register the patient, triage symptoms safely, compute live slots from doctor availability, and complete booking or rescheduling against Supabase with database-backed safeguards. Around that core, the repo also includes a staff-facing Next.js dashboard, seed data for demos, workflow diagrams, and signs of ongoing expansion into broader admin and authentication features.
