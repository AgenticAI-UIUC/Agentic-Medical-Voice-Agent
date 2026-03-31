# Agentic Medical Voice Agent

Voice-powered medical scheduling assistant built with Vapi AI, FastAPI, and Supabase.

## Architecture

- **Backend**: FastAPI (Python 3.11+), managed with `uv`, located in `backend/`
- **Frontend**: Next.js with pnpm, located in `frontend/`
- **Database**: Supabase (Postgres). Schema in `backend/schema.sql`, seed data in `backend/seed.sql`
- **Voice AI**: Vapi handles speech-to-text/text-to-speech; backend exposes tool endpoints that Vapi calls via HTTP

## Backend Structure

```
backend/
├── app/
│   ├── main.py                  # FastAPI app, CORS, router mounting
│   ├── config.py                # Pydantic settings (.env loading)
│   ├── supabase.py              # Supabase client singleton
│   ├── api/
│   │   ├── vapi_auth.py         # Shared-secret auth (x-vapi-secret header)
│   │   ├── vapi_helpers.py      # Tool call parsing, call context cache, response formatting
│   │   ├── vapi_webhook.py      # POST /api/v1/vapi/events (end-of-call transcript saving)
│   │   └── vapi_tools/          # Each file = one or more Vapi tool endpoints
│   │       ├── identify_patient.py  # /identify-patient, /register-patient
│   │       ├── triage.py            # /triage, /list-specialties
│   │       ├── find_slots.py        # /find-slots (+ slot cache)
│   │       ├── book.py              # /book
│   │       ├── reschedule.py        # /find-appointment, /reschedule, /reschedule-finalize
│   │       └── cancel.py            # /cancel
│   └── services/
│       ├── slot_engine.py       # Slot computation, availability, validation
│       ├── time_utils.py        # Timezone/date parsing helpers
│       └── triage_engine.py     # Symptom → specialty matching
├── tests/                       # pytest tests
├── schema.sql                   # Database schema
├── seed.sql                     # Seed data
└── pyproject.toml               # Dependencies (uv)
```

## Key Patterns

### Vapi Tool Contract
All tool endpoints receive payloads in this shape:
```json
{
  "message": {
    "toolCalls": [{"id": "...", "function": {"name": "...", "arguments": "..."}}],
    "call": {"id": "call-uuid"}
  }
}
```
And return:
```json
{"results": [{"toolCallId": "...", "result": "{...}"}]}
```
Use `handle_tool_calls()` from `vapi_helpers.py` to wrap handlers.

### Call Context Cache (`vapi_helpers.py`)
Per-call in-memory cache (keyed by `call_id`, 30-min TTL) that stores `patient_id` and `specialty_id` as they're identified during the call. Downstream tools (`book`, `cancel`, `reschedule`, etc.) fall back to this cache when Vapi's LLM forgets to forward these values.

### Slot Cache (`find_slots.py`, `reschedule.py`)
When slots are offered to the patient, they're cached by `call_id` with a `slot_number`. The `book` and `reschedule-finalize` tools resolve the exact slot from cache, preventing LLM misattribution of doctor_id/times.

## Commands

### Backend
```bash
cd backend
uv run uvicorn app.main:app --reload --port 8000   # Start dev server
uv run pytest tests/ -x -q                          # Run tests
```

### Frontend
```bash
cd frontend
pnpm dev          # Start dev server
```

### Local Development
```bash
ngrok http 8000   # Expose backend for Vapi webhooks
```
The ngrok URL must be configured in the Vapi dashboard for each tool endpoint. URL changes on every ngrok restart (unless using a reserved domain).

## Environment Variables

Defined in `.env` at project root (see `.env.example`):
- `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` — Supabase connection
- `VAPI_WEBHOOK_SECRET` — shared secret for auth (optional in local dev; empty = skip auth)
- `CLINIC_TIMEZONE` — default `America/Chicago`
- `FRONTEND_HOST` — CORS origin, default `http://localhost:5173`

## Important Notes

- All Vapi tool endpoints are protected by `verify_vapi_secret` dependency (skipped when `VAPI_WEBHOOK_SECRET` is empty)
- Slot validation is safety-critical: `validate_slot()` in `slot_engine.py` checks doctor existence, time ranges, availability templates, blocks, and overlaps before any booking
- Reschedule is atomic: new appointment is created BEFORE the old one is cancelled
- The system prompt for the Vapi assistant is in `Medical Voice Agent — System Prompt.md`
