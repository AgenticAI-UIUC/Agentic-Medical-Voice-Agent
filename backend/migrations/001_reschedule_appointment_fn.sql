-- Migration: Create reschedule_appointment function
-- This function atomically inserts a new appointment and cancels the original
-- in a single transaction, preventing partial-failure states.

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
  -- Lock and verify the original appointment is still CONFIRMED
  SELECT id, status
    INTO v_original
    FROM public.appointments
   WHERE id = p_original_appointment_id
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
