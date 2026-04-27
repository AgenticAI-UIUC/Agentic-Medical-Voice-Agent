-- Diagnostic query for Supabase Auth failures like:
--   "Database error creating new user"
--
-- This app stores staff access flags in Supabase Auth metadata and does not
-- require any trigger on auth.users. If user creation fails with that message,
-- run this query in the Supabase SQL editor to find custom auth.users triggers
-- left behind by another starter/template. Those triggers are the usual source
-- of the generic Supabase error.

select
  trigger_name,
  event_manipulation,
  action_timing,
  action_statement
from information_schema.triggers
where event_object_schema = 'auth'
  and event_object_table = 'users'
order by trigger_name;
