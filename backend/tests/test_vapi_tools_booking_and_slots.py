from __future__ import annotations

import pytest

from app.api.vapi_tools import book, find_slots
from tests.support import MockQuery, MockSupabase


def test_handle_find_slots_requires_specialty_or_doctor() -> None:
    result = find_slots._handle_find_slots({}, {})

    assert result == {
        "status": "INVALID",
        "message": "I need to know the specialty to search for available times.",
        "slots": [],
    }


def test_handle_find_slots_returns_doctor_specific_no_slots(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(find_slots, "find_available_slots", lambda *args, **kwargs: [])

    result = find_slots._handle_find_slots({"doctor_id": "doc-1", "preferred_day": "today"}, {})

    assert result["status"] == "NO_SLOTS"
    assert result["slots"] == []


def test_handle_find_slots_formats_specialty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        find_slots,
        "find_slots_for_specialty",
        lambda *args, **kwargs: [
            {"label": "Monday at 9 AM", "doctor_name": "Dr. Alpha"},
            {"label": "Monday at 10 AM", "doctor_name": "Dr. Beta"},
        ],
    )

    result = find_slots._handle_find_slots({"specialty_id": "derm", "preferred_day": "today"}, {})

    assert result["status"] == "OK"
    assert "Monday at 9 AM with Dr. Alpha or Monday at 10 AM with Dr. Beta" in result["message"]


def test_handle_find_slots_formats_same_doctor_results_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        find_slots,
        "find_slots_for_specialty",
        lambda *args, **kwargs: [
            {"label": "Wednesday, April 8 at 2 PM", "doctor_name": "Dr. Priya Patel"},
            {"label": "Wednesday, April 8 at 3 PM", "doctor_name": "Dr. Priya Patel"},
            {"label": "Wednesday, April 8 at 4 PM", "doctor_name": "Dr. Priya Patel"},
        ],
    )

    result = find_slots._handle_find_slots({"specialty_id": "neuro", "preferred_day": "today"}, {})

    assert result["status"] == "OK"
    assert "with Dr. Priya Patel on Wednesday, April 8 at 2 PM, 3 PM or 4 PM" in result["message"]
    assert result["message"].count("Dr. Priya Patel") == 1
    assert result["message"].count("Wednesday, April 8") == 1


def test_handle_find_slots_relaxes_asap_time_bucket_when_no_exact_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
            {"label": "Wednesday, April 8 at 1 PM", "doctor_name": "Dr. Patel"},
            {"label": "Thursday, April 9 at 2 PM", "doctor_name": "Dr. Patel"},
        ]

    monkeypatch.setattr(find_slots, "find_slots_for_specialty", fake_find_slots_for_specialty)

    result = find_slots._handle_find_slots(
        {
            "specialty_id": "neuro",
            "preferred_day": "as soon as possible, please",
            "preferred_time": "morning",
        },
        {},
    )

    assert result["status"] == "OK"
    assert calls == [
        ("neuro", "as soon as possible, please", "morning"),
        ("neuro", "as soon as possible, please", "any"),
    ]
    assert "don't see any morning openings as soon as possible" in result["message"]
    assert "with Dr. Patel: Wednesday, April 8 at 1 PM or Thursday, April 9 at 2 PM" in result["message"]
    assert result["message"].count("Dr. Patel") == 1


def test_handle_find_slots_relaxed_message_collapses_same_day_slots(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_find_slots_for_specialty(
        specialty_id: str,
        preferred_day: str,
        preferred_time: str,
    ) -> list[dict[str, str]]:
        if preferred_time == "morning":
            return []
        return [
            {"label": "Wednesday, April 8 at 2 PM", "doctor_name": "Dr. Patel"},
            {"label": "Wednesday, April 8 at 3 PM", "doctor_name": "Dr. Patel"},
            {"label": "Wednesday, April 8 at 4 PM", "doctor_name": "Dr. Patel"},
        ]

    monkeypatch.setattr(find_slots, "find_slots_for_specialty", fake_find_slots_for_specialty)

    result = find_slots._handle_find_slots(
        {
            "specialty_id": "neuro",
            "preferred_day": "as soon as possible",
            "preferred_time": "morning",
        },
        {},
    )

    assert result["status"] == "OK"
    assert "with Dr. Patel on Wednesday, April 8 at 2 PM, 3 PM or 4 PM" in result["message"]
    assert result["message"].count("Wednesday, April 8") == 1


@pytest.mark.parametrize(
    ("args", "expected_message"),
    [
        ({}, "Missing required booking information."),
        (
            {
                "patient_id": "patient-1",
                "doctor_id": "doctor-1",
                "start_at": "not-a-date",
                "end_at": "2026-04-06T17:00:00Z",
            },
            "I couldn't understand those appointment times. Could you try again?",
        ),
        (
            {
                "patient_id": "patient-1",
                "doctor_id": "doctor-1",
                "start_at": "2026-04-06T17:00:00Z",
                "end_at": "2026-04-06T16:00:00Z",
            },
            "The appointment end time must be after the start time.",
        ),
    ],
)
def test_handle_book_rejects_invalid_inputs(args: dict[str, str], expected_message: str) -> None:
    result = book._handle_book(args, {})

    assert result["status"] == "INVALID"
    assert result["message"] == expected_message


def test_handle_book_surfaces_slot_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(book, "validate_slot", lambda *args, **kwargs: "That slot is already booked.")

    result = book._handle_book(
        {
            "patient_id": "patient-1",
            "doctor_id": "doctor-1",
            "start_at": "2026-04-06T16:00:00Z",
            "end_at": "2026-04-06T17:00:00Z",
        },
        {},
    )

    assert result == {"status": "INVALID", "message": "That slot is already booked."}


def test_handle_book_returns_taken_when_db_constraint_fires(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(book, "validate_slot", lambda *args, **kwargs: None)
    monkeypatch.setattr(book, "get_call_id", lambda payload: "call-123")
    monkeypatch.setattr(book, "format_for_voice", lambda dt: "Monday, April 6 at 11 AM")

    sb = MockSupabase(
        tables={
            "doctors": [MockQuery(data=[{"full_name": "Dr. Adams"}])],
            "appointments": [MockQuery(error=Exception("unique_doctor_appointment"))],
        }
    )
    monkeypatch.setattr(book, "get_supabase", lambda: sb)

    result = book._handle_book(
        {
            "patient_id": "patient-1",
            "doctor_id": "doctor-1",
            "start_at": "2026-04-06T16:00:00Z",
            "end_at": "2026-04-06T17:00:00Z",
        },
        {},
    )

    assert result["status"] == "TAKEN"
    assert "just booked" in result["message"]


def test_handle_book_inserts_appointment_and_returns_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(book, "validate_slot", lambda *args, **kwargs: None)
    monkeypatch.setattr(book, "get_call_id", lambda payload: "call-123")
    monkeypatch.setattr(book, "format_for_voice", lambda dt: "Monday, April 6 at 11 AM")

    insert_query = MockQuery(data=[{"id": "appointment-1"}])
    sb = MockSupabase(
        tables={
            "doctors": [MockQuery(data=[{"full_name": "Dr. Adams"}])],
            "appointments": [insert_query],
        }
    )
    monkeypatch.setattr(book, "get_supabase", lambda: sb)

    result = book._handle_book(
        {
            "patient_id": "patient-1",
            "doctor_id": "doctor-1",
            "specialty_id": "derm",
            "start_at": "2026-04-06T16:00:00Z",
            "end_at": "2026-04-06T17:00:00Z",
            "reason": " follow up ",
            "symptoms": " rash ",
            "severity_description": " itchy ",
        },
        {},
    )

    assert result == {
        "status": "CONFIRMED",
        "appointment_id": "appointment-1",
        "doctor_name": "Dr. Adams",
        "message": "All set — you're booked with Dr. Adams for Monday, April 6 at 11 AM.",
    }
    assert insert_query.inserted_rows[0]["vapi_call_id"] == "call-123"
    assert insert_query.inserted_rows[0]["reason"] == "follow up"
    assert insert_query.inserted_rows[0]["symptoms"] == "rash"
    assert insert_query.inserted_rows[0]["severity_description"] == "itchy"
