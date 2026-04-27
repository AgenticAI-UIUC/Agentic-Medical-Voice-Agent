from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import vapi_webhook
from tests.support import MockQuery, MockSupabase


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(vapi_webhook.router, prefix="/api/v1")
    return TestClient(app)


def test_extract_full_transcript_filters_internal_model_messages() -> None:
    transcript = vapi_webhook._extract_full_transcript(
        {
            "artifact": {
                "messages": [
                    {"role": "system", "message": "private instructions"},
                    {"role": "user", "message": "I need an appointment"},
                    {"role": "assistant", "message": "I can help with that."},
                    {"role": "tool", "message": "{\"status\":\"FOUND\"}"},
                ]
            }
        }
    )

    assert transcript == [
        {"role": "user", "message": "I need an appointment"},
        {"role": "assistant", "message": "I can help with that."},
    ]


def test_save_conversation_inserts_and_links_matching_appointment(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        vapi_webhook,
        "_now_iso",
        lambda: "2026-04-27T12:00:00+00:00",
    )
    existing_query = MockQuery(data=[])
    appointment_lookup = MockQuery(data=[{"id": "appt-1", "patient_id": "patient-1"}])
    insert_query = MockQuery(data=[{"id": "conv-1"}])
    appointment_update = MockQuery(data=[])
    sb = MockSupabase(
        tables={
            "conversations": [existing_query, insert_query],
            "appointments": [appointment_lookup, appointment_update],
        }
    )
    monkeypatch.setattr(vapi_webhook, "get_supabase", lambda: sb)

    vapi_webhook._save_conversation(
        "call-123",
        {
            "artifact": {"messages": [{"role": "assistant", "message": "Hello there"}]},
            "analysis": {"summary": "Booked follow-up"},
        },
    )

    inserted = insert_query.inserted_rows[0]
    assert inserted["call_id"] == "call-123"
    assert inserted["transcript"] == [{"role": "assistant", "message": "Hello there"}]
    assert inserted["summary"] == "Booked follow-up"
    assert inserted["patient_id"] == "patient-1"
    assert inserted["call_status"] == "ended"
    assert inserted["ended_at"] == "2026-04-27T12:00:00+00:00"
    assert inserted["last_event_at"] == "2026-04-27T12:00:00+00:00"
    assert appointment_update.updated_rows == [{"conversation_id": "conv-1"}]


def test_save_conversation_updates_existing_row_for_replayed_webhook(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        vapi_webhook,
        "_now_iso",
        lambda: "2026-04-27T12:00:00+00:00",
    )
    existing_query = MockQuery(data=[{"id": "conv-1"}])
    appointment_lookup = MockQuery(data=[])
    update_query = MockQuery(data=[])
    sb = MockSupabase(
        tables={
            "conversations": [existing_query, update_query],
            "appointments": [appointment_lookup],
        }
    )
    monkeypatch.setattr(vapi_webhook, "get_supabase", lambda: sb)

    vapi_webhook._save_conversation(
        "call-123",
        {
            "artifact": {"messages": [{"role": "assistant", "message": "Hello there"}]},
            "analysis": {"summary": "Booked follow-up"},
        },
    )

    updated = update_query.updated_rows[0]
    assert updated["transcript"] == [{"role": "assistant", "message": "Hello there"}]
    assert updated["summary"] == "Booked follow-up"
    assert updated["call_status"] == "ended"
    assert updated["ended_at"] == "2026-04-27T12:00:00+00:00"
    assert updated["last_event_at"] == "2026-04-27T12:00:00+00:00"
    assert sb.table_calls == ["conversations", "appointments", "conversations"]


def test_conversation_update_filters_system_prompt_before_insert(monkeypatch) -> None:
    monkeypatch.setattr(
        vapi_webhook,
        "_now_iso",
        lambda: "2026-04-27T12:00:00+00:00",
    )
    existing_query = MockQuery(data=[])
    appointment_lookup = MockQuery(data=[])
    insert_query = MockQuery(data=[{"id": "conv-1"}])
    sb = MockSupabase(
        tables={
            "conversations": [existing_query, insert_query],
            "appointments": [appointment_lookup],
        }
    )
    monkeypatch.setattr(vapi_webhook, "get_supabase", lambda: sb)

    vapi_webhook._save_conversation_update(
        "call-123",
        {
            "messagesOpenAIFormatted": [
                {"role": "system", "content": "private instructions"},
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "How can I help?"},
            ]
        },
    )

    inserted = insert_query.inserted_rows[0]
    assert inserted["transcript"] == [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "How can I help?"},
    ]
    assert inserted["call_status"] == "in-progress"


def test_status_update_creates_live_conversation(monkeypatch) -> None:
    monkeypatch.setattr(
        vapi_webhook,
        "_now_iso",
        lambda: "2026-04-27T12:00:00+00:00",
    )
    existing_query = MockQuery(data=[])
    appointment_lookup = MockQuery(data=[])
    insert_query = MockQuery(data=[{"id": "conv-1"}])
    sb = MockSupabase(
        tables={
            "conversations": [existing_query, insert_query],
            "appointments": [appointment_lookup],
        }
    )
    monkeypatch.setattr(vapi_webhook, "get_supabase", lambda: sb)

    vapi_webhook._save_status_update(
        "call-123",
        {"status": "in-progress", "call": {"startedAt": "2026-04-27T11:59:00Z"}},
    )

    assert insert_query.inserted_rows == [
        {
            "call_id": "call-123",
            "transcript": [],
            "call_status": "in-progress",
            "last_event_at": "2026-04-27T12:00:00+00:00",
            "started_at": "2026-04-27T11:59:00Z",
        }
    ]


def test_transcript_update_replaces_partial_with_final(monkeypatch) -> None:
    monkeypatch.setattr(
        vapi_webhook,
        "_now_iso",
        lambda: "2026-04-27T12:00:00+00:00",
    )
    existing_query = MockQuery(
        data=[
            {
                "id": "conv-1",
                "transcript": [
                    {
                        "role": "user",
                        "message": "I need",
                        "transcript_type": "partial",
                    }
                ],
            }
        ]
    )
    appointment_lookup = MockQuery(data=[])
    update_query = MockQuery(data=[])
    sb = MockSupabase(
        tables={
            "conversations": [existing_query, update_query],
            "appointments": [appointment_lookup],
        }
    )
    monkeypatch.setattr(vapi_webhook, "get_supabase", lambda: sb)

    vapi_webhook._save_transcript_update(
        "call-123",
        {
            "role": "user",
            "transcriptType": "final",
            "transcript": "I need an appointment",
        },
        "transcript",
    )

    assert update_query.updated_rows == [
        {
            "call_status": "in-progress",
            "last_event_at": "2026-04-27T12:00:00+00:00",
            "transcript": [
                {
                    "role": "user",
                    "message": "I need an appointment",
                    "transcript_type": "final",
                }
            ],
        }
    ]


def test_vapi_events_handles_sparse_payload_without_crashing(monkeypatch) -> None:
    saved_calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        vapi_webhook,
        "_save_conversation",
        lambda call_id, msg: saved_calls.append((call_id, msg)),
    )

    with _make_client() as client:
        response = client.post(
            "/api/v1/vapi/events",
            json={"message": {"type": "end-of-call-report"}},
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert saved_calls == []


def test_vapi_events_rejects_invalid_secret(monkeypatch) -> None:
    monkeypatch.setattr(vapi_webhook.settings, "VAPI_WEBHOOK_SECRET", "expected-secret")

    with _make_client() as client:
        response = client.post("/api/v1/vapi/events", json={})

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}
