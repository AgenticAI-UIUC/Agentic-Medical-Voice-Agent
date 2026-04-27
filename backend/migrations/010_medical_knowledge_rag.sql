-- Semantic triage knowledge store.
-- Run after the base schema, then ingest chunks with:
--   uv run python -m app.services.ingest_knowledge

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS public.medical_knowledge (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  content text NOT NULL,
  embedding vector(1536),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamp with time zone NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_medical_knowledge_content
  ON public.medical_knowledge (md5(content));

CREATE INDEX IF NOT EXISTS idx_medical_knowledge_embedding
  ON public.medical_knowledge
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

CREATE OR REPLACE FUNCTION public.match_medical_knowledge(
  query_embedding vector(1536),
  match_count int DEFAULT 5,
  match_threshold float DEFAULT 0.3
)
RETURNS TABLE (
  id uuid,
  content text,
  metadata jsonb,
  similarity float
)
LANGUAGE sql STABLE
AS $$
  SELECT
    mk.id,
    mk.content,
    mk.metadata,
    1 - (mk.embedding <=> query_embedding) AS similarity
  FROM public.medical_knowledge mk
  WHERE mk.embedding IS NOT NULL
    AND 1 - (mk.embedding <=> query_embedding) > match_threshold
  ORDER BY mk.embedding <=> query_embedding
  LIMIT match_count;
$$;

GRANT ALL PRIVILEGES ON TABLE public.medical_knowledge TO service_role;
GRANT EXECUTE ON FUNCTION public.match_medical_knowledge(
  vector,
  integer,
  double precision
) TO service_role;
