-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.appointments (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  patient_id uuid NOT NULL,
  doctor_id uuid NOT NULL,
  specialty_id uuid,
  conversation_id uuid,
  follow_up_from_id uuid,
  start_at timestamp with time zone NOT NULL,
  end_at timestamp with time zone NOT NULL,
  reason text,
  symptoms text,
  severity_description text,
  severity_rating integer CHECK (severity_rating >= 1 AND severity_rating <= 10),
  urgency text NOT NULL DEFAULT 'ROUTINE'::text CHECK (urgency = ANY (ARRAY['ROUTINE'::text, 'URGENT'::text, 'ER'::text])),
  status text NOT NULL DEFAULT 'CONFIRMED'::text CHECK (status = ANY (ARRAY['CONFIRMED'::text, 'CANCELLED'::text, 'COMPLETED'::text, 'NO_SHOW'::text])),
  vapi_call_id text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT appointments_pkey PRIMARY KEY (id),
  CONSTRAINT appointments_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES public.patients(id),
  CONSTRAINT appointments_doctor_id_fkey FOREIGN KEY (doctor_id) REFERENCES public.doctors(id),
  CONSTRAINT appointments_specialty_id_fkey FOREIGN KEY (specialty_id) REFERENCES public.specialties(id),
  CONSTRAINT appointments_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id),
  CONSTRAINT appointments_follow_up_from_id_fkey FOREIGN KEY (follow_up_from_id) REFERENCES public.appointments(id)
);
CREATE TABLE public.conversations (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  patient_id uuid,
  call_id text NOT NULL UNIQUE,
  transcript jsonb NOT NULL DEFAULT '[]'::jsonb,
  summary text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT conversations_pkey PRIMARY KEY (id),
  CONSTRAINT conversations_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES public.patients(id)
);
CREATE TABLE public.doctor_availability (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  doctor_id uuid NOT NULL,
  day_of_week integer NOT NULL CHECK (day_of_week >= 0 AND day_of_week <= 6),
  start_time time without time zone NOT NULL,
  end_time time without time zone NOT NULL,
  slot_minutes integer NOT NULL DEFAULT 60 CHECK (slot_minutes > 0),
  timezone text NOT NULL DEFAULT 'America/Chicago'::text,
  CONSTRAINT doctor_availability_pkey PRIMARY KEY (id),
  CONSTRAINT doctor_availability_doctor_id_fkey FOREIGN KEY (doctor_id) REFERENCES public.doctors(id)
);
CREATE TABLE public.doctor_blocks (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  doctor_id uuid NOT NULL,
  start_at timestamp with time zone NOT NULL,
  end_at timestamp with time zone NOT NULL,
  reason text,
  CONSTRAINT doctor_blocks_pkey PRIMARY KEY (id),
  CONSTRAINT doctor_blocks_doctor_id_fkey FOREIGN KEY (doctor_id) REFERENCES public.doctors(id)
);
CREATE TABLE public.doctor_specialties (
  doctor_id uuid NOT NULL,
  specialty_id uuid NOT NULL,
  CONSTRAINT doctor_specialties_pkey PRIMARY KEY (doctor_id, specialty_id),
  CONSTRAINT doctor_specialties_doctor_id_fkey FOREIGN KEY (doctor_id) REFERENCES public.doctors(id),
  CONSTRAINT doctor_specialties_specialty_id_fkey FOREIGN KEY (specialty_id) REFERENCES public.specialties(id)
);
CREATE TABLE public.doctors (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  full_name text NOT NULL,
  image_url text,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT doctors_pkey PRIMARY KEY (id)
);
CREATE TABLE public.patients (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  uin text NOT NULL UNIQUE,
  full_name text NOT NULL,
  phone text NOT NULL UNIQUE CHECK (phone ~ '^\d+$'::text),
  email text,
  allergies text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT patients_pkey PRIMARY KEY (id)
);
CREATE TABLE public.specialties (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  name text NOT NULL UNIQUE,
  description text,
  CONSTRAINT specialties_pkey PRIMARY KEY (id)
);
CREATE TABLE public.symptom_specialty_map (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  symptom text NOT NULL,
  specialty_id uuid NOT NULL,
  weight real NOT NULL DEFAULT 1.0,
  follow_up_questions jsonb,
  CONSTRAINT symptom_specialty_map_pkey PRIMARY KEY (id),
  CONSTRAINT symptom_specialty_map_specialty_id_fkey FOREIGN KEY (specialty_id) REFERENCES public.specialties(id)
);
