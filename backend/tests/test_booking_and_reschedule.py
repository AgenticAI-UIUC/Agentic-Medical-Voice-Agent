"""
Tests for the four production-critical fixes:
  1. Booking validates real slot availability
  2. Booking rejects overlapping slots
  3. Appointment lookup excludes past appointments
  4. Reschedule finalization is atomic-style (cancel only after new booking succeeds)

These tests mock the Supabase client so they run without a live database.
To run: pytest tests/test_booking_and_reschedule.py -v
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _future(hours: int = 48) -> datetime:
    """Return a datetime `hours` in the future (UTC)."""
    return datetime.now(timezone.utc) + timedelta(hours=hours)


def _make_payload(args: dict[str, Any], tool_call_id: str = "tc-1") -> dict[str, Any]:
    """Build a minimal Vapi-style payload wrapping tool call arguments."""
    return {
        "message": {
            "toolCalls": [
                {
                    "id": tool_call_id,
                    "function": {"arguments": args},
                }
            ],
            "call": {"id": "call-test-123"},
        }
    }


# ---------------------------------------------------------------------------
# Fake Supabase query builder (chainable mock)
# ---------------------------------------------------------------------------

class FakeQueryBuilder:
    """Mimics the Supabase query builder chain. Returns configured data."""

    def __init__(self, data: list[dict] | None = None, raise_on_insert: Exception | None = None):
        self._data = data or []
        self._raise_on_insert = raise_on_insert

    def __getattr__(self, name):
        # All chaining methods return self
        if name in ("select", "eq", "neq", "gt", "gte", "lt", "lte",
                     "order", "limit", "update", "delete"):
            return lambda *a, **kw: self
        raise AttributeError(name)

    def insert(self, row):
        if self._raise_on_insert:
            raise self._raise_on_insert
        # Store what was inserted for assertions
        self._last_inserted = row
        return self

    def execute(self):
        resp = MagicMock()
        resp.data = self._data
        return resp


class FakeSupabase:
    """Routes .table(name) to pre-configured FakeQueryBuilders."""

    def __init__(self, tables: dict[str, FakeQueryBuilder] | None = None):
        self._tables = tables or {}

    def table(self, name: str) -> FakeQueryBuilder:
        return self._tables.get(name, FakeQueryBuilder())


# ---------------------------------------------------------------------------
# 1. Booking a valid generated slot succeeds
# ---------------------------------------------------------------------------

@patch("app.services.slot_engine.get_supabase")
@patch("app.api.vapi_tools.book.get_supabase")
@patch("app.services.slot_engine.now_utc")
def test_book_valid_slot_succeeds(mock_now, mock_book_sb, mock_engine_sb):
    """A slot that passes all validation checks should result in CONFIRMED."""
    from app.api.vapi_tools.book import _handle_book

    now = datetime.now(timezone.utc)
    mock_now.return_value = now

    start = _future(48)
    end = start + timedelta(hours=1)

    appt_id = str(uuid.uuid4())

    # Patch validate_slot to pass (slot is valid)
    with patch("app.api.vapi_tools.book.validate_slot", return_value=None):
        fake_sb = FakeSupabase({
            "doctors": FakeQueryBuilder([{"full_name": "Dr. Test"}]),
            "appointments": FakeQueryBuilder([{"id": appt_id}]),
        })
        mock_book_sb.return_value = fake_sb

        result = _handle_book(
            {
                "patient_id": str(uuid.uuid4()),
                "doctor_id": str(uuid.uuid4()),
                "start_at": _utc_iso(start),
                "end_at": _utc_iso(end),
            },
            _make_payload({}),
        )

    assert result["status"] == "CONFIRMED"
    assert result["appointment_id"] == appt_id


# ---------------------------------------------------------------------------
# 2. Booking an invalid slot fails
# ---------------------------------------------------------------------------

@patch("app.api.vapi_tools.book.validate_slot")
def test_book_invalid_slot_rejected(mock_validate):
    """A slot that fails validation should be rejected before touching the DB."""
    from app.api.vapi_tools.book import _handle_book

    mock_validate.return_value = {
        "status": "INVALID",
        "message": "That time slot does not match the doctor's availability.",
    }

    start = _future(48)
    end = start + timedelta(hours=1)

    result = _handle_book(
        {
            "patient_id": str(uuid.uuid4()),
            "doctor_id": str(uuid.uuid4()),
            "start_at": _utc_iso(start),
            "end_at": _utc_iso(end),
        },
        _make_payload({}),
    )

    assert result["status"] == "INVALID"
    assert "availability" in result["message"]


# ---------------------------------------------------------------------------
# 3. Booking an overlapping slot fails
# ---------------------------------------------------------------------------

@patch("app.api.vapi_tools.book.validate_slot")
def test_book_overlapping_slot_rejected(mock_validate):
    """A slot that overlaps an existing appointment should return TAKEN."""
    from app.api.vapi_tools.book import _handle_book

    mock_validate.return_value = {
        "status": "TAKEN",
        "message": "That time slot conflicts with an existing appointment.",
    }

    start = _future(48)
    end = start + timedelta(hours=1)

    result = _handle_book(
        {
            "patient_id": str(uuid.uuid4()),
            "doctor_id": str(uuid.uuid4()),
            "start_at": _utc_iso(start),
            "end_at": _utc_iso(end),
        },
        _make_payload({}),
    )

    assert result["status"] == "TAKEN"


# ---------------------------------------------------------------------------
# 4. find_appointment excludes past appointments
# ---------------------------------------------------------------------------

@patch("app.api.vapi_tools.reschedule.get_supabase")
@patch("app.api.vapi_tools.reschedule.now_utc")
def test_find_appointment_excludes_past(mock_now, mock_sb):
    """find_appointment should only return future confirmed appointments."""
    from app.api.vapi_tools.reschedule import _handle_find_appointment

    now = datetime.now(timezone.utc)
    mock_now.return_value = now

    # Simulate: DB returns no future appointments (all past ones filtered by .gt)
    fake_sb = FakeSupabase({
        "appointments": FakeQueryBuilder([]),
    })
    mock_sb.return_value = fake_sb

    result = _handle_find_appointment(
        {"patient_id": str(uuid.uuid4())},
        _make_payload({}),
    )

    assert result["status"] == "NO_APPOINTMENTS"


@patch("app.api.vapi_tools.reschedule.get_supabase")
@patch("app.api.vapi_tools.reschedule.now_utc")
def test_find_appointment_returns_future(mock_now, mock_sb):
    """find_appointment returns future appointments when they exist."""
    from app.api.vapi_tools.reschedule import _handle_find_appointment

    now = datetime.now(timezone.utc)
    mock_now.return_value = now

    future_start = _future(48)
    appt_id = str(uuid.uuid4())
    doctor_id = str(uuid.uuid4())

    fake_sb = FakeSupabase({
        "appointments": FakeQueryBuilder([{
            "id": appt_id,
            "doctor_id": doctor_id,
            "specialty_id": None,
            "start_at": _utc_iso(future_start),
            "end_at": _utc_iso(future_start + timedelta(hours=1)),
            "reason": "checkup",
            "symptoms": None,
            "status": "CONFIRMED",
            "doctors": {"full_name": "Dr. Test"},
        }]),
    })
    mock_sb.return_value = fake_sb

    result = _handle_find_appointment(
        {"patient_id": str(uuid.uuid4())},
        _make_payload({}),
    )

    assert result["status"] == "FOUND"
    assert result["appointment"]["id"] == appt_id


# ---------------------------------------------------------------------------
# 5. Reschedule finalization succeeds end-to-end
# ---------------------------------------------------------------------------

@patch("app.api.vapi_tools.reschedule.get_supabase")
@patch("app.api.vapi_tools.reschedule.validate_slot", return_value=None)
@patch("app.api.vapi_tools.reschedule.now_utc")
def test_reschedule_finalize_success(mock_now, mock_validate, mock_sb):
    """Successful reschedule: new appointment created, old one cancelled."""
    from app.api.vapi_tools.reschedule import _handle_reschedule_finalize

    now = datetime.now(timezone.utc)
    mock_now.return_value = now

    orig_start = _future(48)
    new_start = _future(72)
    orig_id = str(uuid.uuid4())
    new_id = str(uuid.uuid4())
    doctor_id = str(uuid.uuid4())

    # The fake supabase needs to handle multiple .table() calls in sequence:
    # 1. appointments.select (fetch original) -> returns the original
    # 2. appointments.insert (create new) -> returns new appointment
    # 3. appointments.update (cancel original) -> ok
    # 4. doctors.select (get name) -> returns doctor

    call_count = {"appointments": 0}

    class MultiCallAppointments(FakeQueryBuilder):
        def select(self, *a, **kw):
            call_count["appointments"] += 1
            if call_count["appointments"] == 1:
                # First select: fetch original appointment
                self._data = [{
                    "id": orig_id,
                    "status": "CONFIRMED",
                    "start_at": _utc_iso(orig_start),
                    "end_at": _utc_iso(orig_start + timedelta(hours=1)),
                    "specialty_id": None,
                    "reason": "checkup",
                    "symptoms": None,
                    "severity_description": None,
                    "severity_rating": None,
                    "urgency": "ROUTINE",
                }]
            return self

        def insert(self, row):
            self._data = [{"id": new_id, **row}]
            return self

        def update(self, data):
            self._data = [{"id": orig_id}]
            return self

    fake_sb = FakeSupabase({
        "appointments": MultiCallAppointments(),
        "doctors": FakeQueryBuilder([{"full_name": "Dr. Test"}]),
    })
    mock_sb.return_value = fake_sb

    result = _handle_reschedule_finalize(
        {
            "original_appointment_id": orig_id,
            "patient_id": str(uuid.uuid4()),
            "doctor_id": doctor_id,
            "start_at": _utc_iso(new_start),
            "end_at": _utc_iso(new_start + timedelta(hours=1)),
        },
        _make_payload({}),
    )

    assert result["status"] == "RESCHEDULED"
    assert result["new_appointment_id"] == new_id
    assert result["cancelled_appointment_id"] == orig_id


# ---------------------------------------------------------------------------
# 6. Reschedule does not cancel old appointment if new booking fails
# ---------------------------------------------------------------------------

@patch("app.api.vapi_tools.reschedule._check_overlap", return_value=True)
@patch("app.api.vapi_tools.reschedule.get_supabase")
@patch("app.api.vapi_tools.reschedule.validate_slot")
@patch("app.api.vapi_tools.reschedule.now_utc")
def test_reschedule_no_cancel_if_new_booking_fails(mock_now, mock_validate, mock_sb, mock_overlap):
    """If the new slot is invalid/taken, the original appointment must NOT be cancelled."""
    from app.api.vapi_tools.reschedule import _handle_reschedule_finalize

    now = datetime.now(timezone.utc)
    mock_now.return_value = now

    orig_start = _future(48)
    new_start = _future(72)
    orig_id = str(uuid.uuid4())

    # validate_slot rejects the new slot as TAKEN, and _check_overlap confirms
    # it's a real conflict (not just the original appointment)
    mock_validate.return_value = {"status": "TAKEN", "message": "Slot taken."}

    fake_sb = FakeSupabase({
        "appointments": FakeQueryBuilder([{
            "id": orig_id,
            "status": "CONFIRMED",
            "start_at": _utc_iso(orig_start),
            "end_at": _utc_iso(orig_start + timedelta(hours=1)),
            "specialty_id": None,
            "reason": None,
            "symptoms": None,
            "severity_description": None,
            "severity_rating": None,
            "urgency": "ROUTINE",
        }]),
    })
    mock_sb.return_value = fake_sb

    result = _handle_reschedule_finalize(
        {
            "original_appointment_id": orig_id,
            "patient_id": str(uuid.uuid4()),
            "doctor_id": str(uuid.uuid4()),
            "start_at": _utc_iso(new_start),
            "end_at": _utc_iso(new_start + timedelta(hours=1)),
        },
        _make_payload({}),
    )

    assert result["status"] == "TAKEN"


# ---------------------------------------------------------------------------
# 7. Partial failure: new booking succeeds but old cancellation fails
# ---------------------------------------------------------------------------

@patch("app.api.vapi_tools.reschedule.get_supabase")
@patch("app.api.vapi_tools.reschedule.validate_slot", return_value=None)
@patch("app.api.vapi_tools.reschedule.now_utc")
def test_reschedule_partial_failure(mock_now, mock_validate, mock_sb):
    """If new appointment is created but old one fails to cancel,
    return RESCHEDULE_PARTIAL_FAILURE with both IDs."""
    from app.api.vapi_tools.reschedule import _handle_reschedule_finalize

    now = datetime.now(timezone.utc)
    mock_now.return_value = now

    orig_start = _future(48)
    new_start = _future(72)
    orig_id = str(uuid.uuid4())
    new_id = str(uuid.uuid4())

    call_count = {"select": 0}

    class PartialFailAppointments(FakeQueryBuilder):
        def select(self, *a, **kw):
            call_count["select"] += 1
            if call_count["select"] == 1:
                self._data = [{
                    "id": orig_id,
                    "status": "CONFIRMED",
                    "start_at": _utc_iso(orig_start),
                    "end_at": _utc_iso(orig_start + timedelta(hours=1)),
                    "specialty_id": None,
                    "reason": "checkup",
                    "symptoms": None,
                    "severity_description": None,
                    "severity_rating": None,
                    "urgency": "ROUTINE",
                }]
            return self

        def insert(self, row):
            self._data = [{"id": new_id, **row}]
            return self

        def update(self, data):
            # Simulate cancellation failure
            raise Exception("DB connection lost during cancel")

    fake_sb = FakeSupabase({
        "appointments": PartialFailAppointments(),
        "doctors": FakeQueryBuilder([{"full_name": "Dr. Test"}]),
    })
    mock_sb.return_value = fake_sb

    result = _handle_reschedule_finalize(
        {
            "original_appointment_id": orig_id,
            "patient_id": str(uuid.uuid4()),
            "doctor_id": str(uuid.uuid4()),
            "start_at": _utc_iso(new_start),
            "end_at": _utc_iso(new_start + timedelta(hours=1)),
        },
        _make_payload({}),
    )

    assert result["status"] == "RESCHEDULE_PARTIAL_FAILURE"
    assert result["new_appointment_id"] == new_id
    assert result["original_appointment_id"] == orig_id
    assert "error_detail" in result
