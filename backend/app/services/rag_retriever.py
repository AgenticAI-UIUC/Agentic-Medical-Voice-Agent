from __future__ import annotations

import json
from typing import Any, TypedDict, cast

import httpx

from app.config import settings
from app.supabase import get_supabase

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
OPENAI_EMBEDDING_URL = "https://api.openai.com/v1/embeddings"


class RetrievedMedicalKnowledge(TypedDict):
    id: str
    content: str
    metadata: dict[str, Any]
    similarity: float


def _get_openai_api_key() -> str:
    api_key = settings.OPENAI_API_KEY.strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    return api_key


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts with the same model used for ingestion."""
    api_key = _get_openai_api_key()

    response = httpx.post(
        OPENAI_EMBEDDING_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": EMBEDDING_MODEL,
            "input": texts,
            "dimensions": EMBEDDING_DIMENSIONS,
        },
        timeout=60.0,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"OpenAI embedding API error ({response.status_code}): {response.text}"
        )

    data = response.json()
    embedding_objects = sorted(data["data"], key=lambda obj: obj["index"])
    return [obj["embedding"] for obj in embedding_objects]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]


def retrieve_medical_knowledge(
    query: str,
    *,
    match_count: int = 5,
    match_threshold: float = 0.3,
) -> list[RetrievedMedicalKnowledge]:
    """Semantic search over embedded triage knowledge in Supabase pgvector."""
    normalized_query = query.strip()
    if not normalized_query:
        return []

    query_embedding = embed_query(normalized_query)
    result = (
        get_supabase()
        .rpc(
            "match_medical_knowledge",
            {
                "query_embedding": query_embedding,
                "match_count": match_count,
                "match_threshold": match_threshold,
            },
        )
        .execute()
    )

    rows = cast(list[dict[str, Any]], getattr(result, "data", None) or [])
    chunks: list[RetrievedMedicalKnowledge] = []
    for row in rows:
        metadata = row.get("metadata", {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        if not isinstance(metadata, dict):
            metadata = {}

        chunks.append(
            {
                "id": str(row.get("id") or ""),
                "content": str(row.get("content") or ""),
                "metadata": metadata,
                "similarity": float(row.get("similarity") or 0.0),
            }
        )

    return chunks
