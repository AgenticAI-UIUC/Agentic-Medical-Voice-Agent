-- Migration: Add CHECK constraints ensuring end > start on time-range columns

ALTER TABLE public.appointments
  ADD CONSTRAINT chk_appointments_end_after_start CHECK (end_at > start_at);

ALTER TABLE public.doctor_blocks
  ADD CONSTRAINT chk_doctor_blocks_end_after_start CHECK (end_at > start_at);

ALTER TABLE public.doctor_availability
  ADD CONSTRAINT chk_availability_end_after_start CHECK (end_time > start_time);
