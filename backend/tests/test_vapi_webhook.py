from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import vapi_webhook
from tests.support import MockQuery, MockSupabase


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(vapi_webhook.router, prefix="/api/v1")
    return TestClient(app)


def test_save_conversation_inserts_and_links_matching_appointment(
    monkeypatch,
) -> None:
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

    assert insert_query.inserted_rows == [
        {
            "call_id": "call-123",
            "transcript": [{"role": "assistant", "message": "Hello there"}],
            "summary": "Booked follow-up",
            "patient_id": "patient-1",
        }
    ]
    assert appointment_update.updated_rows == [{"conversation_id": "conv-1"}]


def test_save_conversation_updates_existing_row_for_replayed_webhook(
    monkeypatch,
) -> None:
    existing_query = MockQuery(data=[{"id": "conv-1"}])
    update_query = MockQuery(data=[])
    sb = MockSupabase(tables={"conversations": [existing_query, update_query]})
    monkeypatch.setattr(vapi_webhook, "get_supabase", lambda: sb)

    vapi_webhook._save_conversation(
        "call-123",
        {
            "transcript": [{"role": "user", "message": "I need an appointment"}],
            "analysis": {"summary": "Replay payload"},
        },
    )

    assert update_query.updated_rows == [
        {
            "transcript": [{"role": "user", "message": "I need an appointment"}],
            "summary": "Replay payload",
        }
    ]
    assert sb.table_calls == ["conversations", "conversations"]


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
