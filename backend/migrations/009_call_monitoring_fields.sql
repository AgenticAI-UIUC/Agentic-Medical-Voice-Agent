ALTER TABLE public.conversations
  ADD COLUMN IF NOT EXISTS call_status text NOT NULL DEFAULT 'unknown',
  ADD COLUMN IF NOT EXISTS outcome text,
  ADD COLUMN IF NOT EXISTS ended_reason text,
  ADD COLUMN IF NOT EXISTS started_at timestamp with time zone,
  ADD COLUMN IF NOT EXISTS ended_at timestamp with time zone,
  ADD COLUMN IF NOT EXISTS last_event_at timestamp with time zone NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS conversations_last_event_at_idx
  ON public.conversations (last_event_at DESC);

CREATE INDEX IF NOT EXISTS conversations_call_status_idx
  ON public.conversations (call_status);
