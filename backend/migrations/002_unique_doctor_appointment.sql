-- Migration: Add unique constraint to prevent double-booking
-- Ensures no two CONFIRMED appointments can exist for the same doctor
-- at the same start time. The Python code in book.py and reschedule.py
-- already catches "unique_doctor_appointment" errors, but the constraint
-- was never created in the database.

CREATE UNIQUE INDEX unique_doctor_appointment
  ON public.appointments (doctor_id, start_at)
  WHERE (status = 'CONFIRMED');
