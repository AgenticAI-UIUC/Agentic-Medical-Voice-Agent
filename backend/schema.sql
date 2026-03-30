-- ============================================================
-- Medical Voice Agent — Final Schema
--
-- Built from the project workflow document. Supports:
--   - Patient registration with human-readable UIN
--   - Symptom triage → specialty matching (iterative)
--   - Specialty-based doctor lookup
--   - Computed slot availability (no pre-generated slots)
--   - Booking, rescheduling, cancellation
--   - Follow-up appointments linking to previous ones
--   - Local conversation/transcript storage for search
-- ============================================================

-- ============================================================
-- 1. Lookup / reference tables
-- ============================================================

-- Specialties (e.g. "Cardiology", "Dermatology", "General Practice")
CREATE TABLE public.specialties (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name        text NOT NULL UNIQUE,
  description text
);

-- Symptoms → specialty mapping (the "symptoms database" for triage)
-- Used by the triage tool to iteratively narrow down specialty
CREATE TABLE public.symptom_specialty_map (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  symptom       text NOT NULL,             -- e.g. "chest pain", "rash", "headache"
  specialty_id  uuid NOT NULL REFERENCES public.specialties(id) ON DELETE CASCADE,
  weight        real NOT NULL DEFAULT 1.0, -- higher = stronger signal for this specialty
  follow_up_questions jsonb,               -- extra questions to ask if this symptom alone isn't enough
  CONSTRAINT unique_symptom_specialty UNIQUE (symptom, specialty_id)
);

-- ============================================================
-- 2. Doctors
-- ============================================================

CREATE TABLE public.doctors (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name  text    NOT NULL,
  image_url  text,
  is_active  boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Doctor ↔ Specialty (many-to-many)
CREATE TABLE public.doctor_specialties (
  doctor_id    uuid NOT NULL REFERENCES public.doctors(id) ON DELETE CASCADE,
  specialty_id uuid NOT NULL REFERENCES public.specialties(id) ON DELETE CASCADE,
  PRIMARY KEY (doctor_id, specialty_id)
);

-- Doctor weekly availability template
-- Breaks modeled as separate rows: e.g. Mon 9:00–12:00 + Mon 13:00–17:00
CREATE TABLE public.doctor_availability (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  doctor_id    uuid    NOT NULL REFERENCES public.doctors(id) ON DELETE CASCADE,
  day_of_week  integer NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),  -- 0=Sun, 6=Sat
  start_time   time    NOT NULL,
  end_time     time    NOT NULL,
  slot_minutes integer NOT NULL DEFAULT 60 CHECK (slot_minutes > 0),
  timezone     text    NOT NULL DEFAULT 'America/Chicago',
  CONSTRAINT valid_window CHECK (start_time < end_time)
);

-- Doctor blocks (one-off unavailability: sick days, meetings, vacations)
CREATE TABLE public.doctor_blocks (
  id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  doctor_id uuid        NOT NULL REFERENCES public.doctors(id) ON DELETE CASCADE,
  start_at  timestamptz NOT NULL,
  end_at    timestamptz NOT NULL,
  reason    text,
  CONSTRAINT valid_block_window CHECK (start_at < end_at)
);

-- ============================================================
-- 3. Patients
-- ============================================================

-- UIN is a 9-digit identifier patients speak over the phone
CREATE TABLE public.patients (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  uin        text        NOT NULL UNIQUE,  -- 9-digit, spoken over phone
  full_name  text        NOT NULL,
  phone      text        NOT NULL UNIQUE,
  email      text,
  allergies  text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT phone_digits_only CHECK (phone ~ '^\d{10,15}$'),
  CONSTRAINT uin_format CHECK (uin ~ '^\d{9}$')
);

-- ============================================================
-- 4. Conversations (call transcripts stored locally for search)
-- ============================================================

CREATE TABLE public.conversations (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id uuid        REFERENCES public.patients(id),
  call_id    text        NOT NULL UNIQUE,  -- Vapi call ID
  transcript jsonb       NOT NULL DEFAULT '[]'::jsonb,
  summary    text,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- ============================================================
-- 5. Appointments
-- ============================================================

CREATE TABLE public.appointments (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id          uuid        NOT NULL REFERENCES public.patients(id),
  doctor_id           uuid        NOT NULL REFERENCES public.doctors(id),
  specialty_id        uuid        REFERENCES public.specialties(id),
  conversation_id     uuid        REFERENCES public.conversations(id),
  -- Link to previous appointment (for follow-ups)
  follow_up_from_id   uuid        REFERENCES public.appointments(id),
  -- Time
  start_at            timestamptz NOT NULL,
  end_at              timestamptz NOT NULL,
  -- Clinical info collected during triage
  reason              text,         -- free-text reason for visit
  symptoms            text,         -- symptoms described by patient
  severity_description text,        -- patient's own words about severity
  severity_rating     integer       CHECK (severity_rating BETWEEN 1 AND 10),
  urgency             text          NOT NULL DEFAULT 'ROUTINE'
                        CHECK (urgency IN ('ROUTINE', 'URGENT', 'ER')),
  -- Status
  status              text          NOT NULL DEFAULT 'CONFIRMED'
                        CHECK (status IN ('CONFIRMED', 'CANCELLED', 'COMPLETED', 'NO_SHOW')),
  -- Vapi metadata
  vapi_call_id        text,
  -- Timestamps
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),
  -- Prevent double-booking
  CONSTRAINT unique_doctor_appointment UNIQUE (doctor_id, start_at),
  CONSTRAINT valid_appointment_window  CHECK (start_at < end_at)
);

-- ============================================================
-- 5b. Exclusion constraint: prevent overlapping confirmed appointments
-- ============================================================

-- Required for GiST-based exclusion constraints on non-geometric types.
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- SAFETY-CRITICAL: Prevent any two active (non-cancelled) appointments for the
-- same doctor from overlapping in time. The simple UNIQUE on (doctor_id, start_at)
-- is insufficient because two appointments with different start times can still
-- overlap (e.g. 9:00–10:00 and 9:30–10:30).
--
-- This exclusion constraint uses a partial index scoped to active statuses only,
-- so cancelled/completed/no-show appointments do not block future bookings.
ALTER TABLE public.appointments
  ADD CONSTRAINT no_overlapping_confirmed
  EXCLUDE USING gist (
    doctor_id WITH =,
    tstzrange(start_at, end_at) WITH &&
  )
  WHERE (status NOT IN ('CANCELLED'));

-- ============================================================
-- 6. Indexes
-- ============================================================

-- Find booked appointments for a doctor in a date range (for computing available slots)
CREATE INDEX idx_appointments_doctor_time
  ON public.appointments (doctor_id, start_at, end_at)
  WHERE status NOT IN ('CANCELLED');

-- Find blocks for a doctor in a date range
CREATE INDEX idx_blocks_doctor_time
  ON public.doctor_blocks (doctor_id, start_at, end_at);

-- Patient lookup by UIN (used on every call for identification)
CREATE INDEX idx_patients_uin
  ON public.patients (uin);

-- Patient lookup by phone
CREATE INDEX idx_patients_phone
  ON public.patients (phone);

-- Find appointments for a patient (for rescheduling/cancellation lookup)
CREATE INDEX idx_appointments_patient
  ON public.appointments (patient_id, created_at DESC)
  WHERE status = 'CONFIRMED';

-- Symptom lookup for triage
CREATE INDEX idx_symptom_map_symptom
  ON public.symptom_specialty_map (symptom);

-- Doctor lookup by specialty (for finding available doctors)
CREATE INDEX idx_doctor_specialties_specialty
  ON public.doctor_specialties (specialty_id);

-- Conversation lookup by patient (for transcript search)
CREATE INDEX idx_conversations_patient
  ON public.conversations (patient_id, created_at DESC);

-- ============================================================
-- 7. Triggers
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_appointments_updated_at
  BEFORE UPDATE ON public.appointments
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at();
