from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.services import rag_retriever
from tests.support import MockQuery, MockSupabase


def test_get_openai_api_key_requires_configuration(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(rag_retriever.settings, "OPENAI_API_KEY", "")

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is not configured"):
        rag_retriever._get_openai_api_key()


def test_embed_texts_sorts_embeddings_by_index(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    def fake_post(
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
        timeout: float,
    ) -> SimpleNamespace:
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return SimpleNamespace(
            status_code=200,
            json=lambda: {
                "data": [
                    {"index": 1, "embedding": [2.0, 2.1]},
                    {"index": 0, "embedding": [1.0, 1.1]},
                ]
            },
        )

    monkeypatch.setattr(rag_retriever.settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(rag_retriever.httpx, "post", fake_post)

    result = rag_retriever.embed_texts(["first", "second"])

    assert captured["url"] == rag_retriever.OPENAI_EMBEDDING_URL
    assert captured["timeout"] == 60.0
    assert captured["json"] == {
        "model": rag_retriever.EMBEDDING_MODEL,
        "input": ["first", "second"],
        "dimensions": rag_retriever.EMBEDDING_DIMENSIONS,
    }
    assert result == [[1.0, 1.1], [2.0, 2.1]]


def test_embed_texts_raises_on_http_error(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(rag_retriever.settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        rag_retriever.httpx,
        "post",
        lambda *args, **kwargs: SimpleNamespace(
            status_code=500,
            text="upstream failure",
        ),
    )

    with pytest.raises(RuntimeError, match="OpenAI embedding API error"):
        rag_retriever.embed_texts(["query"])


def test_retrieve_medical_knowledge_parses_rpc_rows(
    monkeypatch: pytest.MonkeyPatch,
):
    sb = MockSupabase(
        rpcs={
            "match_medical_knowledge": [
                MockQuery(
                    data=[
                        {
                            "id": "chunk-1",
                            "content": "Cardiology content",
                            "metadata": json.dumps(
                                {
                                    "specialty_id": "spec-cardio",
                                    "specialty_name": "Cardiology",
                                }
                            ),
                            "similarity": 0.88,
                        }
                    ]
                )
            ]
        }
    )
    monkeypatch.setattr(rag_retriever, "get_supabase", lambda: sb)
    monkeypatch.setattr(rag_retriever, "embed_query", lambda query: [0.1, 0.2])

    result = rag_retriever.retrieve_medical_knowledge(
        "chest pressure",
        match_count=3,
        match_threshold=0.4,
    )

    assert sb.rpc_calls == [
        (
            "match_medical_knowledge",
            {
                "query_embedding": [0.1, 0.2],
                "match_count": 3,
                "match_threshold": 0.4,
            },
        )
    ]
    assert result == [
        {
            "id": "chunk-1",
            "content": "Cardiology content",
            "metadata": {
                "specialty_id": "spec-cardio",
                "specialty_name": "Cardiology",
            },
            "similarity": 0.88,
        }
    ]


def test_retrieve_medical_knowledge_returns_empty_list(
    monkeypatch: pytest.MonkeyPatch,
):
    sb = MockSupabase(rpcs={"match_medical_knowledge": [MockQuery(data=[])]})
    monkeypatch.setattr(rag_retriever, "get_supabase", lambda: sb)
    monkeypatch.setattr(rag_retriever, "embed_query", lambda query: [0.1, 0.2])

    assert rag_retriever.retrieve_medical_knowledge("no results") == []
