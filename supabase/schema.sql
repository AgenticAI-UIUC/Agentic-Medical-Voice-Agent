-- Supabase/Postgres schema bootstrap
-- Run from Supabase SQL editor or via psql against your project database.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.profiles (
  id uuid PRIMARY KEY REFERENCES auth.users(id),
  full_name text,
  role text NOT NULL DEFAULT 'STAFF'::text
    CHECK (role = ANY (ARRAY['ADMIN'::text, 'STAFF'::text])),
  created_at timestamp with time zone NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.specialties (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS public.doctors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name text NOT NULL,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  image_url text,
  user_id uuid UNIQUE REFERENCES public.profiles(id)
);

CREATE TABLE IF NOT EXISTS public.doctor_availability (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  doctor_id uuid NOT NULL REFERENCES public.doctors(id),
  day_of_week integer NOT NULL CHECK (day_of_week >= 0 AND day_of_week <= 6),
  start_time time without time zone NOT NULL,
  end_time time without time zone NOT NULL,
  slot_minutes integer NOT NULL DEFAULT 60
    CHECK (slot_minutes = ANY (ARRAY[15, 20, 30, 60])),
  break_start time without time zone,
  break_end time without time zone,
  timezone text NOT NULL DEFAULT 'America/Chicago'::text,
  created_by uuid REFERENCES public.profiles(id)
);

CREATE TABLE IF NOT EXISTS public.appointments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name text NOT NULL,
  phone text NOT NULL,
  preferred_day text NOT NULL,
  preferred_time text NOT NULL,
  reason text,
  urgency text NOT NULL DEFAULT 'ROUTINE'::text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  vapi_call_id text,
  caller_phone text,
  appointment_ref text,
  call_type text,
  vapi_tool_call_id text,
  doctor_id uuid REFERENCES public.doctors(id),
  slot_id uuid,
  created_by uuid REFERENCES public.profiles(id)
);

CREATE TABLE IF NOT EXISTS public.appointment_slots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  doctor_id uuid NOT NULL REFERENCES public.doctors(id),
  start_at timestamp with time zone NOT NULL,
  end_at timestamp with time zone NOT NULL,
  status text NOT NULL DEFAULT 'AVAILABLE'::text
    CHECK (status = ANY (ARRAY['AVAILABLE'::text, 'BOOKED'::text, 'BLOCKED'::text])),
  appointment_id uuid REFERENCES public.appointments(id),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  created_by uuid REFERENCES public.profiles(id)
);

CREATE TABLE IF NOT EXISTS public.doctor_specialties (
  doctor_id uuid NOT NULL REFERENCES public.doctors(id),
  specialty_id uuid NOT NULL REFERENCES public.specialties(id),
  PRIMARY KEY (doctor_id, specialty_id)
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'appointments_slot_id_fkey'
      AND conrelid = 'public.appointments'::regclass
  ) THEN
    ALTER TABLE public.appointments
      ADD CONSTRAINT appointments_slot_id_fkey
      FOREIGN KEY (slot_id)
      REFERENCES public.appointment_slots(id);
  END IF;
END $$;
