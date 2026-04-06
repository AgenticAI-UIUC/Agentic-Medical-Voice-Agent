-- Migration: Replace unique index with exclusion constraint for overlap prevention
--
-- The old unique index (doctor_id, start_at) only prevented exact same-start
-- double-bookings. This exclusion constraint prevents any overlapping time
-- ranges for the same doctor, which is the correct business rule.

-- Required for GiST index on uuid + tstzrange
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- Drop the old weaker constraint
ALTER TABLE public.appointments DROP CONSTRAINT IF EXISTS unique_doctor_appointment;

-- Add exclusion constraint: no two CONFIRMED appointments for the same doctor
-- may have overlapping time ranges.
ALTER TABLE public.appointments
  ADD CONSTRAINT no_doctor_overlap
  EXCLUDE USING gist (
    doctor_id WITH =,
    tstzrange(start_at, end_at) WITH &&
  )
  WHERE (status = 'CONFIRMED');
