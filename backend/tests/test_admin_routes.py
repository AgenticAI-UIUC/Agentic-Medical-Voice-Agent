from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.admin import routes
from tests.support import MockQuery, MockSupabase


def test_cancel_appointment_marks_confirmed_appointment_cancelled(monkeypatch) -> None:
    lookup_query = MockQuery(data=[{"id": "appt-1", "status": "CONFIRMED"}])
    update_query = MockQuery(data=[{"id": "appt-1", "status": "CANCELLED"}])
    sb = MockSupabase(tables={"appointments": [lookup_query, update_query]})
    monkeypatch.setattr(routes, "get_supabase", lambda: sb)

    result = routes.cancel_appointment("appt-1", SimpleNamespace())

    assert result == {"id": "appt-1", "status": "CANCELLED"}
    assert update_query.updated_rows[0]["status"] == "CANCELLED"
    assert "updated_at" in update_query.updated_rows[0]
    assert ("eq", ("id", "appt-1"), {}) in update_query.calls


def test_cancel_appointment_rejects_non_confirmed_appointment(monkeypatch) -> None:
    lookup_query = MockQuery(data=[{"id": "appt-1", "status": "COMPLETED"}])
    sb = MockSupabase(tables={"appointments": [lookup_query]})
    monkeypatch.setattr(routes, "get_supabase", lambda: sb)

    with pytest.raises(HTTPException) as exc_info:
        routes.cancel_appointment("appt-1", SimpleNamespace())

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Only confirmed appointments can be cancelled"
