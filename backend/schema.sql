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
  CONSTRAINT chk_appointments_end_after_start CHECK (end_at > start_at),
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
ALTER TABLE public.appointments
  ADD CONSTRAINT no_doctor_overlap
  EXCLUDE USING gist (
    doctor_id WITH =,
    tstzrange(start_at, end_at) WITH &&
  )
  WHERE (status = 'CONFIRMED');
CREATE TABLE public.conversations (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  patient_id uuid,
  call_id text NOT NULL UNIQUE,
  transcript jsonb NOT NULL DEFAULT '[]'::jsonb,
  summary text,
  call_status text NOT NULL DEFAULT 'unknown'::text,
  outcome text,
  ended_reason text,
  started_at timestamp with time zone,
  ended_at timestamp with time zone,
  last_event_at timestamp with time zone NOT NULL DEFAULT now(),
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
  CONSTRAINT chk_availability_end_after_start CHECK (end_time > start_time),
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
  CONSTRAINT chk_doctor_blocks_end_after_start CHECK (end_at > start_at),
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
  uin text NOT NULL UNIQUE CHECK (uin ~ '^\d{9}$'::text),
  full_name text NOT NULL,
  phone text NOT NULL CHECK (phone ~ '^\d+$'::text),
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
  CONSTRAINT unique_symptom_specialty UNIQUE (symptom, specialty_id),
  CONSTRAINT symptom_specialty_map_specialty_id_fkey FOREIGN KEY (specialty_id) REFERENCES public.specialties(id)
);

-- Atomically insert a new appointment and cancel the original in one transaction.
-- Returns a JSON object with status, new_appointment_id, and original_appointment_id.
CREATE OR REPLACE FUNCTION public.reschedule_appointment(
  p_original_appointment_id uuid,
  p_patient_id uuid,
  p_doctor_id uuid,
  p_start_at timestamptz,
  p_end_at timestamptz,
  p_specialty_id uuid DEFAULT NULL,
  p_reason text DEFAULT NULL,
  p_symptoms text DEFAULT NULL,
  p_severity_description text DEFAULT NULL,
  p_severity_rating integer DEFAULT NULL,
  p_urgency text DEFAULT 'ROUTINE',
  p_vapi_call_id text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
  v_original record;
  v_new_id uuid;
BEGIN
  -- Lock and verify the original appointment is still CONFIRMED and belongs to this patient
  SELECT id, status
    INTO v_original
    FROM public.appointments
   WHERE id = p_original_appointment_id
     AND patient_id = p_patient_id
     FOR UPDATE;

  IF NOT FOUND THEN
    RETURN jsonb_build_object('status', 'NOT_FOUND');
  END IF;

  IF v_original.status <> 'CONFIRMED' THEN
    RETURN jsonb_build_object('status', 'NOT_ACTIVE');
  END IF;

  -- Insert the new appointment
  INSERT INTO public.appointments (
    patient_id, doctor_id, start_at, end_at, specialty_id,
    reason, symptoms, severity_description, severity_rating,
    urgency, status, vapi_call_id
  ) VALUES (
    p_patient_id, p_doctor_id, p_start_at, p_end_at, p_specialty_id,
    p_reason, p_symptoms, p_severity_description, p_severity_rating,
    p_urgency, 'CONFIRMED', p_vapi_call_id
  )
  RETURNING id INTO v_new_id;

  -- Cancel the original appointment
  UPDATE public.appointments
     SET status = 'CANCELLED', updated_at = now()
   WHERE id = p_original_appointment_id;

  RETURN jsonb_build_object(
    'status', 'RESCHEDULED',
    'new_appointment_id', v_new_id,
    'original_appointment_id', p_original_appointment_id
  );
END;
$$;
