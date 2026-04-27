from __future__ import annotations

import sys
import time
from typing import Any

from app.config import settings
from app.services.knowledge_chunks import KNOWLEDGE_CHUNKS
from app.services.rag_retriever import embed_texts
from app.supabase import get_supabase


def _require_openai_api_key() -> None:
    if settings.OPENAI_API_KEY.strip():
        return
    print(
        "ERROR: OPENAI_API_KEY is not configured.\n"
        "Add it to .env before ingesting semantic triage knowledge."
    )
    sys.exit(1)


def ingest_chunks() -> None:
    """Embed starter triage knowledge and save it in medical_knowledge."""
    _require_openai_api_key()
    sb = get_supabase()

    print(f"Found {len(KNOWLEDGE_CHUNKS)} knowledge chunks to process")
    chunks_to_embed: list[dict[str, Any]] = []

    for index, chunk in enumerate(KNOWLEDGE_CHUNKS, 1):
        content = str(chunk["content"])
        metadata = chunk["metadata"]
        existing = (
            sb.table("medical_knowledge")
            .select("id,embedding")
            .eq("content", content)
            .limit(1)
            .execute()
        )
        rows = getattr(existing, "data", None) or []
        if rows:
            row = rows[0]
            if row.get("embedding"):
                print(f"[{index}/{len(KNOWLEDGE_CHUNKS)}] Skip: {content[:72]}...")
                continue
            print(
                f"[{index}/{len(KNOWLEDGE_CHUNKS)}] Existing row needs embedding: "
                f"{content[:72]}..."
            )
            chunks_to_embed.append({"id": row["id"], "content": content})
            continue

        inserted = (
            sb.table("medical_knowledge")
            .insert(
                {
                    "content": content,
                    "metadata": metadata if isinstance(metadata, dict) else {},
                }
            )
            .execute()
        )
        inserted_rows = getattr(inserted, "data", None) or []
        if not inserted_rows:
            print(f"[{index}/{len(KNOWLEDGE_CHUNKS)}] Failed insert: {content[:72]}...")
            continue

        row_id = inserted_rows[0]["id"]
        print(f"[{index}/{len(KNOWLEDGE_CHUNKS)}] Inserted: {content[:72]}...")
        chunks_to_embed.append({"id": row_id, "content": content})

    if not chunks_to_embed:
        print("All chunks already have embeddings.")
        return

    print(f"Embedding {len(chunks_to_embed)} chunks...")
    started = time.time()
    embeddings = embed_texts([chunk["content"] for chunk in chunks_to_embed])
    print(f"Embedding complete in {time.time() - started:.1f}s")

    for chunk, embedding in zip(chunks_to_embed, embeddings):
        (
            sb.table("medical_knowledge")
            .update({"embedding": embedding})
            .eq("id", chunk["id"])
            .execute()
        )

    print(f"Saved {len(chunks_to_embed)} embeddings.")


if __name__ == "__main__":
    ingest_chunks()
