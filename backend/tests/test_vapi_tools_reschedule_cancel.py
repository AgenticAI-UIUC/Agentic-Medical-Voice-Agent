from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.api.vapi_tools import cancel, reschedule
from app.services import slot_engine as slot_engine_service
from tests.support import MockQuery, MockSupabase


VALID_APPOINTMENT_ID = "11111111-1111-1111-1111-111111111111"
VALID_PATIENT_ID = "22222222-2222-2222-2222-222222222222"
VALID_DOCTOR_ID = "33333333-3333-3333-3333-333333333333"
FIXED_NOW = datetime(2026, 4, 1, tzinfo=timezone.utc)


def test_handle_find_appointment_requires_patient_id() -> None:
    result = reschedule._handle_find_appointment({}, {})

    assert result["status"] == "INVALID"


def test_handle_find_appointment_returns_found_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    appointments = [
        {
            "id": VALID_APPOINTMENT_ID,
            "doctor_id": VALID_DOCTOR_ID,
            "specialty_id": "derm",
            "start_at": "2026-04-10T16:00:00Z",
            "end_at": "2026-04-10T17:00:00Z",
            "reason": "follow up",
            "symptoms": "rash",
            "status": "CONFIRMED",
            "doctors": {"full_name": "Dr. Adams"},
        }
    ]
    sb = MockSupabase(tables={"appointments": [MockQuery(data=appointments)]})
    monkeypatch.setattr(reschedule, "get_supabase", lambda: sb)
    monkeypatch.setattr(reschedule, "now_utc", lambda: FIXED_NOW)
    monkeypatch.setattr(
        reschedule, "_format_start", lambda start_at: "Friday, April 10 at 11 AM"
    )

    result = reschedule._handle_find_appointment(
        {"patient_id": VALID_PATIENT_ID, "doctor_name": "adams"},
        {},
    )

    assert result["status"] == "FOUND"
    assert result["appointment"]["id"] == VALID_APPOINTMENT_ID
    assert "Friday, April 10 at 11 AM" in result["message"]


def test_handle_find_appointment_supports_follow_up_lookup_with_completed_visit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    appointments = [
        {
            "id": VALID_APPOINTMENT_ID,
            "doctor_id": VALID_DOCTOR_ID,
            "specialty_id": "gp",
            "start_at": "2026-04-01T16:00:00Z",
            "end_at": "2026-04-01T17:00:00Z",
            "reason": "Annual checkup",
            "symptoms": "general checkup",
            "status": "COMPLETED",
            "doctors": {"full_name": "Dr. Sarah Chen"},
        }
    ]
    sb = MockSupabase(tables={"appointments": [MockQuery(data=appointments)]})
    monkeypatch.setattr(reschedule, "get_supabase", lambda: sb)
    monkeypatch.setattr(
        reschedule, "_format_start", lambda start_at: "Wednesday, April 1 at 11 AM"
    )

    result = reschedule._handle_find_appointment(
        {
            "patient_id": VALID_PATIENT_ID,
            "doctor_name": "Sarah Chen",
            "reason": "follow up",
            "include_past": True,
        },
        {},
    )

    assert result["status"] == "FOUND"
    assert result["appointment"]["id"] == VALID_APPOINTMENT_ID
    assert result["appointment"]["doctor_name"] == "Dr. Sarah Chen"


def test_handle_find_appointment_treats_false_string_as_false_for_include_past(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    appointments = [
        {
            "id": VALID_APPOINTMENT_ID,
            "doctor_id": VALID_DOCTOR_ID,
            "specialty_id": "gp",
            "start_at": "2026-04-01T16:00:00Z",
            "end_at": "2026-04-01T17:00:00Z",
            "reason": "Annual checkup",
            "symptoms": "general checkup",
            "status": "COMPLETED",
            "doctors": {"full_name": "Dr. Sarah Chen"},
        }
    ]
    sb = MockSupabase(tables={"appointments": [MockQuery(data=appointments)]})
    monkeypatch.setattr(reschedule, "get_supabase", lambda: sb)
    monkeypatch.setattr(reschedule, "now_utc", lambda: FIXED_NOW)

    result = reschedule._handle_find_appointment(
        {
            "patient_id": VALID_PATIENT_ID,
            "include_past": "false",
        },
        {},
    )

    assert result["status"] == "NO_APPOINTMENTS"


def test_handle_find_appointment_returns_multiple_choices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    appointments = [
        {
            "id": VALID_APPOINTMENT_ID,
            "doctor_id": VALID_DOCTOR_ID,
            "specialty_id": "derm",
            "start_at": "2026-04-10T16:00:00Z",
            "end_at": "2026-04-10T17:00:00Z",
            "reason": "follow up",
            "symptoms": "rash",
            "status": "CONFIRMED",
            "doctors": {"full_name": "Dr. Adams"},
        },
        {
            "id": "44444444-4444-4444-4444-444444444444",
            "doctor_id": "55555555-5555-5555-5555-555555555555",
            "specialty_id": "cardiology",
            "start_at": "2026-04-11T16:00:00Z",
            "end_at": "2026-04-11T17:00:00Z",
            "reason": "palpitations",
            "symptoms": "palpitations",
            "status": "CONFIRMED",
            "doctors": {"full_name": "Dr. Baker"},
        },
    ]
    sb = MockSupabase(tables={"appointments": [MockQuery(data=appointments)]})
    monkeypatch.setattr(reschedule, "get_supabase", lambda: sb)
    monkeypatch.setattr(reschedule, "now_utc", lambda: FIXED_NOW)
    monkeypatch.setattr(
        reschedule, "_format_start", lambda start_at: f"slot-for-{start_at[:10]}"
    )

    result = reschedule._handle_find_appointment({"patient_id": VALID_PATIENT_ID}, {})

    assert result["status"] == "MULTIPLE"
    assert len(result["appointments"]) == 2


def test_handle_reschedule_rejects_invalid_appointment_id() -> None:
    result = reschedule._handle_reschedule(
        {"appointment_id": "not-a-uuid", "patient_id": VALID_PATIENT_ID},
        {},
    )

    assert result["status"] == "INVALID"


def test_handle_reschedule_returns_no_slots(monkeypatch: pytest.MonkeyPatch) -> None:
    sb = MockSupabase(
        tables={
            "appointments": [
                MockQuery(
                    data=[
                        {
                            "id": VALID_APPOINTMENT_ID,
                            "specialty_id": "derm",
                            "doctor_id": VALID_DOCTOR_ID,
                            "status": "CONFIRMED",
                        }
                    ]
                )
            ]
        }
    )
    monkeypatch.setattr(reschedule, "get_supabase", lambda: sb)
    monkeypatch.setattr(
        reschedule, "find_slots_for_specialty", lambda *args, **kwargs: []
    )

    result = reschedule._handle_reschedule(
        {
            "appointment_id": VALID_APPOINTMENT_ID,
            "patient_id": VALID_PATIENT_ID,
            "preferred_day": "next week",
        },
        {},
    )

    assert result["status"] == "NO_SLOTS"


def test_handle_reschedule_normalizes_non_string_preferences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sb = MockSupabase(
        tables={
            "appointments": [
                MockQuery(
                    data=[
                        {
                            "id": VALID_APPOINTMENT_ID,
                            "specialty_id": "derm",
                            "doctor_id": VALID_DOCTOR_ID,
                            "status": "CONFIRMED",
                        }
                    ]
                )
            ]
        }
    )
    calls: list[tuple[str, str, str]] = []

    def fake_find_slots_for_specialty(
        specialty_id: str,
        preferred_day: str,
        preferred_time: str,
    ) -> list[dict[str, str]]:
        calls.append((specialty_id, preferred_day, preferred_time))
        return []

    monkeypatch.setattr(reschedule, "get_supabase", lambda: sb)
    monkeypatch.setattr(
        reschedule, "find_slots_for_specialty", fake_find_slots_for_specialty
    )

    result = reschedule._handle_reschedule(
        {
            "appointment_id": VALID_APPOINTMENT_ID,
            "patient_id": VALID_PATIENT_ID,
            "preferred_day": 42,
            "preferred_time": ["morning"],
        },
        {},
    )

    assert result["status"] == "NO_SLOTS"
    assert calls == [("derm", "", "")]


def test_handle_reschedule_relaxes_asap_time_bucket_when_no_exact_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sb = MockSupabase(
        tables={
            "appointments": [
                MockQuery(
                    data=[
                        {
                            "id": VALID_APPOINTMENT_ID,
                            "specialty_id": "neuro",
                            "doctor_id": VALID_DOCTOR_ID,
                            "status": "CONFIRMED",
                        }
                    ]
                )
            ]
        }
    )
    calls: list[tuple[str, str, str]] = []

    def fake_find_slots_for_specialty(
        specialty_id: str,
        preferred_day: str,
        preferred_time: str,
    ) -> list[dict[str, str]]:
        calls.append((specialty_id, preferred_day, preferred_time))
        if preferred_time == "morning":
            return []
        return [
            {
                "doctor_id": VALID_DOCTOR_ID,
                "start_at": "2026-04-08T18:00:00Z",
                "end_at": "2026-04-08T19:00:00Z",
                "label": "Wednesday, April 8 at 1 PM",
            }
        ]

    monkeypatch.setattr(reschedule, "get_supabase", lambda: sb)
    monkeypatch.setattr(
        reschedule, "find_slots_for_specialty", fake_find_slots_for_specialty
    )

    result = reschedule._handle_reschedule(
        {
            "appointment_id": VALID_APPOINTMENT_ID,
            "patient_id": VALID_PATIENT_ID,
            "preferred_day": "as soon as possible, please",
            "preferred_time": "morning",
        },
        {},
    )

    assert result["status"] == "SLOTS_AVAILABLE"
    assert calls == [
        ("neuro", "as soon as possible, please", "morning"),
        ("neuro", "as soon as possible, please", "any"),
    ]
    assert "don't see any morning openings as soon as possible" in result["message"]


def test_handle_reschedule_allows_missing_patient_id_when_appointment_is_known(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sb = MockSupabase(
        tables={
            "appointments": [
                MockQuery(
                    data=[
                        {
                            "id": VALID_APPOINTMENT_ID,
                            "patient_id": VALID_PATIENT_ID,
                            "specialty_id": "derm",
                            "doctor_id": VALID_DOCTOR_ID,
                            "status": "CONFIRMED",
                        }
                    ]
                )
            ]
        }
    )
    monkeypatch.setattr(reschedule, "get_supabase", lambda: sb)
    monkeypatch.setattr(
        reschedule,
        "find_slots_for_specialty",
        lambda *args, **kwargs: [
            {
                "doctor_id": VALID_DOCTOR_ID,
                "start_at": "2026-04-16T14:00:00Z",
                "end_at": "2026-04-16T15:00:00Z",
                "label": "Thursday, April 16 at 9 AM",
            }
        ],
    )

    result = reschedule._handle_reschedule(
        {
            "appointment_id": VALID_APPOINTMENT_ID,
            "preferred_day": "next week",
            "preferred_time": "morning",
        },
        {},
    )

    assert result["status"] == "SLOTS_AVAILABLE"
    assert result["patient_id"] == VALID_PATIENT_ID


def test_handle_reschedule_falls_back_to_same_doctor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sb = MockSupabase(
        tables={
            "appointments": [
                MockQuery(
                    data=[
                        {
                            "id": VALID_APPOINTMENT_ID,
                            "specialty_id": None,
                            "doctor_id": VALID_DOCTOR_ID,
                            "status": "CONFIRMED",
                        }
                    ]
                )
            ]
        }
    )
    monkeypatch.setattr(reschedule, "get_supabase", lambda: sb)
    monkeypatch.setattr(
        slot_engine_service,
        "find_available_slots",
        lambda *args, **kwargs: [
            {
                "start_at": "2026-04-12T16:00:00Z",
                "end_at": "2026-04-12T17:00:00Z",
                "label": "Sunday, April 12 at 11 AM",
            }
        ],
    )

    result = reschedule._handle_reschedule(
        {
            "appointment_id": VALID_APPOINTMENT_ID,
            "patient_id": VALID_PATIENT_ID,
            "preferred_day": "next week",
        },
        {},
    )

    assert result["status"] == "SLOTS_AVAILABLE"
    assert result["slots"][0]["doctor_id"] == VALID_DOCTOR_ID


def test_handle_reschedule_finalize_rejects_invalid_datetimes() -> None:
    result = reschedule._handle_reschedule_finalize(
        {
            "original_appointment_id": VALID_APPOINTMENT_ID,
            "patient_id": VALID_PATIENT_ID,
            "doctor_id": VALID_DOCTOR_ID,
            "start_at": "bad",
            "end_at": "still-bad",
        },
        {},
    )

    assert result["status"] == "INVALID"
    assert "couldn't understand" in result["message"]


def test_handle_reschedule_finalize_rejects_end_before_start() -> None:
    result = reschedule._handle_reschedule_finalize(
        {
            "original_appointment_id": VALID_APPOINTMENT_ID,
            "patient_id": VALID_PATIENT_ID,
            "doctor_id": VALID_DOCTOR_ID,
            "start_at": "2026-04-10T17:00:00Z",
            "end_at": "2026-04-10T16:00:00Z",
        },
        {},
    )

    assert result == {
        "status": "INVALID",
        "message": "The appointment end time must be after the start time.",
    }


def test_handle_reschedule_finalize_sanitizes_optional_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(reschedule, "validate_slot", lambda *args, **kwargs: None)
    monkeypatch.setattr(reschedule, "get_call_id", lambda payload: "call-999")
    monkeypatch.setattr(
        reschedule, "format_for_voice", lambda dt: "Friday, April 10 at 11 AM"
    )

    sb = MockSupabase(
        tables={
            "appointments": [
                MockQuery(
                    data=[
                        {
                            "id": VALID_APPOINTMENT_ID,
                            "specialty_id": "derm",
                            "reason": "follow up",
                            "symptoms": "rash",
                            "severity_description": None,
                            "severity_rating": None,
                            "urgency": "ROUTINE",
                        }
                    ]
                )
            ],
            "doctors": [MockQuery(data=[{"full_name": "Dr. Adams"}])],
        },
        rpcs={
            "reschedule_appointment": [
                MockQuery(
                    data={"status": "RESCHEDULED", "new_appointment_id": "new-appt"}
                )
            ]
        },
    )
    monkeypatch.setattr(reschedule, "get_supabase", lambda: sb)

    result = reschedule._handle_reschedule_finalize(
        {
            "original_appointment_id": VALID_APPOINTMENT_ID,
            "patient_id": VALID_PATIENT_ID,
            "doctor_id": VALID_DOCTOR_ID,
            "start_at": "2026-04-10T16:00:00Z",
            "end_at": "2026-04-10T17:00:00Z",
            "specialty_id": ["bad"],
            "reason": 5,
        },
        {},
    )

    assert result["status"] == "RESCHEDULED"
    assert sb.rpc_calls[0][1]["p_specialty_id"] == "derm"
    assert sb.rpc_calls[0][1]["p_reason"] == "follow up"


def test_handle_reschedule_finalize_maps_rpc_not_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(reschedule, "validate_slot", lambda *args, **kwargs: None)
    monkeypatch.setattr(reschedule, "get_call_id", lambda payload: "call-123")
    monkeypatch.setattr(
        reschedule, "format_for_voice", lambda dt: "Friday, April 10 at 11 AM"
    )

    sb = MockSupabase(
        tables={
            "appointments": [
                MockQuery(
                    data=[
                        {
                            "id": VALID_APPOINTMENT_ID,
                            "specialty_id": "derm",
                            "reason": "follow up",
                            "symptoms": "rash",
                            "severity_description": None,
                            "severity_rating": None,
                            "urgency": "ROUTINE",
                        }
                    ]
                )
            ],
            "doctors": [MockQuery(data=[{"full_name": "Dr. Adams"}])],
        },
        rpcs={"reschedule_appointment": [MockQuery(data={"status": "NOT_ACTIVE"})]},
    )
    monkeypatch.setattr(reschedule, "get_supabase", lambda: sb)

    result = reschedule._handle_reschedule_finalize(
        {
            "original_appointment_id": VALID_APPOINTMENT_ID,
            "patient_id": VALID_PATIENT_ID,
            "doctor_id": VALID_DOCTOR_ID,
            "start_at": "2026-04-10T16:00:00Z",
            "end_at": "2026-04-10T17:00:00Z",
        },
        {},
    )

    assert result == {
        "status": "INVALID",
        "message": "The original appointment is no longer active.",
    }


def test_handle_reschedule_finalize_returns_rescheduled_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(reschedule, "validate_slot", lambda *args, **kwargs: None)
    monkeypatch.setattr(reschedule, "get_call_id", lambda payload: "call-123")
    monkeypatch.setattr(
        reschedule, "format_for_voice", lambda dt: "Friday, April 10 at 11 AM"
    )

    sb = MockSupabase(
        tables={
            "appointments": [
                MockQuery(
                    data=[
                        {
                            "id": VALID_APPOINTMENT_ID,
                            "specialty_id": "derm",
                            "reason": "follow up",
                            "symptoms": "rash",
                            "severity_description": None,
                            "severity_rating": None,
                            "urgency": "ROUTINE",
                        }
                    ]
                )
            ],
            "doctors": [MockQuery(data=[{"full_name": "Dr. Adams"}])],
        },
        rpcs={
            "reschedule_appointment": [
                MockQuery(
                    data={"status": "RESCHEDULED", "new_appointment_id": "new-appt"}
                )
            ]
        },
    )
    monkeypatch.setattr(reschedule, "get_supabase", lambda: sb)

    result = reschedule._handle_reschedule_finalize(
        {
            "original_appointment_id": VALID_APPOINTMENT_ID,
            "patient_id": VALID_PATIENT_ID,
            "doctor_id": VALID_DOCTOR_ID,
            "start_at": "2026-04-10T16:00:00Z",
            "end_at": "2026-04-10T17:00:00Z",
        },
        {},
    )

    assert result == {
        "status": "RESCHEDULED",
        "appointment_id": "new-appt",
        "original_appointment_id": VALID_APPOINTMENT_ID,
        "doctor_name": "Dr. Adams",
        "message": (
            "Your appointment has been rescheduled. You're now booked with "
            "Dr. Adams on Friday, April 10 at 11 AM. Your previous appointment has been cancelled."
        ),
    }
    assert sb.rpc_calls[0][0] == "reschedule_appointment"


def test_handle_cancel_rejects_invalid_uuid() -> None:
    result = cancel._handle_cancel({"appointment_id": "bad-id"}, {})

    assert result["status"] == "INVALID"


def test_handle_cancel_updates_appointment_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    select_query = MockQuery(
        data=[
            {
                "id": VALID_APPOINTMENT_ID,
                "status": "CONFIRMED",
                "doctors": {"full_name": "Dr. Adams"},
            }
        ]
    )
    update_query = MockQuery(data=[])
    sb = MockSupabase(tables={"appointments": [select_query, update_query]})
    monkeypatch.setattr(cancel, "get_supabase", lambda: sb)

    result = cancel._handle_cancel({"appointment_id": VALID_APPOINTMENT_ID}, {})

    assert result == {
        "status": "CANCELLED",
        "appointment_id": VALID_APPOINTMENT_ID,
        "message": "Your appointment with Dr. Adams has been cancelled.",
    }
    assert update_query.updated_rows == [{"status": "CANCELLED"}]
