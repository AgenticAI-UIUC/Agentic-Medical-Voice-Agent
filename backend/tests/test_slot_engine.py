from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services import slot_engine
from tests.support import MockQuery, MockSupabase


def test_generate_theoretical_slots_builds_utc_slots_from_local_availability() -> None:
    availability = [
        {
            "day_of_week": 1,
            "start_time": "09:00:00",
            "end_time": "11:00:00",
            "slot_minutes": 60,
            "timezone": "America/Chicago",
        }
    ]

    slots = slot_engine._generate_theoretical_slots(
        availability,
        datetime(2026, 4, 6, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 4, 7, 0, 0, tzinfo=timezone.utc),
    )

    assert slots == [
        (
            datetime(2026, 4, 6, 14, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 6, 15, 0, tzinfo=timezone.utc),
        ),
        (
            datetime(2026, 4, 6, 15, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 6, 16, 0, tzinfo=timezone.utc),
        ),
    ]


def test_find_available_slots_filters_past_booked_and_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_now = datetime(2026, 4, 6, 14, 30, tzinfo=timezone.utc)
    theoretical_slots = [
        (
            datetime(2026, 4, 6, 14, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 6, 15, 0, tzinfo=timezone.utc),
        ),
        (
            datetime(2026, 4, 6, 16, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 6, 17, 0, tzinfo=timezone.utc),
        ),
        (
            datetime(2026, 4, 6, 17, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 6, 18, 0, tzinfo=timezone.utc),
        ),
        (
            datetime(2026, 4, 6, 18, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 6, 19, 0, tzinfo=timezone.utc),
        ),
        (
            datetime(2026, 4, 6, 19, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 6, 20, 0, tzinfo=timezone.utc),
        ),
    ]

    monkeypatch.setattr(slot_engine, "now_utc", lambda: fixed_now)
    monkeypatch.setattr(slot_engine, "_fetch_availability", lambda doctor_id: [{"configured": True}])
    monkeypatch.setattr(
        slot_engine,
        "_fetch_booked",
        lambda doctor_id, start_utc, end_utc: {
            datetime(2026, 4, 6, 16, 0, tzinfo=timezone.utc)
        },
    )
    monkeypatch.setattr(
        slot_engine,
        "_fetch_blocks",
        lambda doctor_id, start_utc, end_utc: [
            (
                datetime(2026, 4, 6, 17, 0, tzinfo=timezone.utc),
                datetime(2026, 4, 6, 18, 0, tzinfo=timezone.utc),
            )
        ],
    )
    monkeypatch.setattr(slot_engine, "_generate_theoretical_slots", lambda *args: theoretical_slots)
    monkeypatch.setattr(slot_engine, "format_for_voice", lambda dt: f"slot-{dt.hour}")

    slots = slot_engine.find_available_slots("doc-1", "next available", "any", max_slots=2)

    assert slots == [
        {
            "start_at": "2026-04-06T18:00:00+00:00",
            "end_at": "2026-04-06T19:00:00+00:00",
            "label": "slot-18",
        },
        {
            "start_at": "2026-04-06T19:00:00+00:00",
            "end_at": "2026-04-06T20:00:00+00:00",
            "label": "slot-19",
        },
    ]


def test_find_slots_for_specialty_combines_active_doctors_and_sorts(monkeypatch: pytest.MonkeyPatch) -> None:
    specialty_rows = [
        {"doctor_id": "doc-b", "doctors": {"id": "doc-b", "full_name": "Dr. Beta", "is_active": True}},
        {"doctor_id": "doc-c", "doctors": {"id": "doc-c", "full_name": "Dr. Closed", "is_active": False}},
        {"doctor_id": "doc-a", "doctors": {"id": "doc-a", "full_name": "Dr. Alpha", "is_active": True}},
    ]
    sb = MockSupabase(tables={"doctor_specialties": [MockQuery(data=specialty_rows)]})
    monkeypatch.setattr(slot_engine, "get_supabase", lambda: sb)

    def fake_find_available_slots(
        doctor_id: str,
        preferred_day: str,
        preferred_time: str,
        max_slots: int = 5,
    ) -> list[dict[str, str]]:
        if doctor_id == "doc-a":
            return [{"start_at": "2026-04-06T20:00:00+00:00", "end_at": "2026-04-06T21:00:00+00:00", "label": "late"}]
        if doctor_id == "doc-b":
            return [{"start_at": "2026-04-06T18:00:00+00:00", "end_at": "2026-04-06T19:00:00+00:00", "label": "early"}]
        return []

    monkeypatch.setattr(slot_engine, "find_available_slots", fake_find_available_slots)

    slots = slot_engine.find_slots_for_specialty("cardiology", "today", "any", max_slots=5)

    assert slots == [
        {
            "start_at": "2026-04-06T18:00:00+00:00",
            "end_at": "2026-04-06T19:00:00+00:00",
            "label": "early",
            "doctor_id": "doc-b",
            "doctor_name": "Dr. Beta",
        },
        {
            "start_at": "2026-04-06T20:00:00+00:00",
            "end_at": "2026-04-06T21:00:00+00:00",
            "label": "late",
            "doctor_id": "doc-a",
            "doctor_name": "Dr. Alpha",
        },
    ]


@pytest.mark.parametrize(
    ("start_dt", "end_dt", "expected"),
    [
        (
            datetime(2026, 4, 6, 13, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 6, 14, 0, tzinfo=timezone.utc),
            "That time has already passed. Please choose a future time.",
        ),
        (
            datetime(2026, 4, 21, 15, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 21, 16, 0, tzinfo=timezone.utc),
            f"We can only book up to {slot_engine.settings.SCHEDULING_HORIZON_DAYS} days out. Please choose an earlier date.",
        ),
    ],
)
def test_validate_slot_enforces_time_guards(
    monkeypatch: pytest.MonkeyPatch,
    start_dt: datetime,
    end_dt: datetime,
    expected: str,
) -> None:
    monkeypatch.setattr(slot_engine, "now_utc", lambda: datetime(2026, 4, 6, 14, 0, tzinfo=timezone.utc))

    def fail_get_supabase() -> None:
        raise AssertionError("validate_slot should stop before database access")

    monkeypatch.setattr(slot_engine, "get_supabase", fail_get_supabase)

    assert slot_engine.validate_slot("doc-1", start_dt, end_dt) == expected


def test_validate_slot_returns_overlap_error_for_confirmed_appointment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(slot_engine, "now_utc", lambda: datetime(2026, 4, 6, 14, 0, tzinfo=timezone.utc))
    monkeypatch.setattr(
        slot_engine,
        "_fetch_availability",
        lambda doctor_id: [
            {
                "day_of_week": 1,
                "start_time": "10:00:00",
                "end_time": "12:00:00",
                "slot_minutes": 60,
                "timezone": "America/Chicago",
            }
        ],
    )
    monkeypatch.setattr(slot_engine, "_fetch_blocks", lambda doctor_id, start_dt, end_dt: [])

    sb = MockSupabase(
        tables={
            "doctors": [MockQuery(data=[{"id": "doc-1", "is_active": True}])],
            "appointments": [MockQuery(data=[{"id": "existing"}])],
        }
    )
    monkeypatch.setattr(slot_engine, "get_supabase", lambda: sb)

    error = slot_engine.validate_slot(
        "doc-1",
        datetime(2026, 4, 6, 16, 0, tzinfo=timezone.utc),
        datetime(2026, 4, 6, 17, 0, tzinfo=timezone.utc),
    )

    assert error == "That slot is already booked."


def test_validate_slot_accepts_valid_available_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(slot_engine, "now_utc", lambda: datetime(2026, 4, 6, 14, 0, tzinfo=timezone.utc))
    monkeypatch.setattr(
        slot_engine,
        "_fetch_availability",
        lambda doctor_id: [
            {
                "day_of_week": 1,
                "start_time": "10:00:00",
                "end_time": "12:00:00",
                "slot_minutes": 60,
                "timezone": "America/Chicago",
            }
        ],
    )
    monkeypatch.setattr(slot_engine, "_fetch_blocks", lambda doctor_id, start_dt, end_dt: [])

    sb = MockSupabase(
        tables={
            "doctors": [MockQuery(data=[{"id": "doc-1", "is_active": True}])],
            "appointments": [MockQuery(data=[])],
        }
    )
    monkeypatch.setattr(slot_engine, "get_supabase", lambda: sb)

    assert slot_engine.validate_slot(
        "doc-1",
        datetime(2026, 4, 6, 16, 0, tzinfo=timezone.utc),
        datetime(2026, 4, 6, 17, 0, tzinfo=timezone.utc),
    ) is None
