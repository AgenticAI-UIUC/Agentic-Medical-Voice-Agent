-- This app stores staff access state in Supabase Auth metadata:
--   app_metadata.is_active
--   app_metadata.is_superuser
--   user_metadata.full_name
--
-- It does not require a database trigger on auth.users. A leftover trigger
-- named on_auth_user_created can cause Supabase Auth to fail with:
--   "Database error creating new user"
--
-- Run this in the Supabase SQL editor to unblock Auth user creation.

drop trigger if exists on_auth_user_created on auth.users;

-- Intentionally leave handle_new_user() in place. Other code may still refer
-- to it, and dropping the trigger is enough to stop Auth sign-up failures.
