from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch


def _utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _future(hours: int = 48) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours)


def _make_payload(args: dict[str, Any], tool_call_id: str = "tc-1") -> dict[str, Any]:
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


class FakeQueryBuilder:
    def __init__(self, data: list[dict] | None = None, raise_on_insert: Exception | None = None):
        self._data = data or []
        self._raise_on_insert = raise_on_insert

    def __getattr__(self, name):
        if name in ("select", "eq", "neq", "gt", "gte", "lt", "lte", "order", "limit", "update", "delete"):
            return lambda *a, **kw: self
        raise AttributeError(name)

    def insert(self, row):
        if self._raise_on_insert:
            raise self._raise_on_insert
        self._last_inserted = row
        return self

    def execute(self):
        resp = MagicMock()
        resp.data = self._data
        return resp


class FakeSupabase:
    def __init__(self, tables: dict[str, FakeQueryBuilder] | None = None):
        self._tables = tables or {}

    def table(self, name: str) -> FakeQueryBuilder:
        return self._tables.get(name, FakeQueryBuilder())


class SymptomMapQuery:
    def __init__(self, rows_by_term: dict[str, list[dict[str, Any]]]):
        self._rows_by_term = rows_by_term
        self._term = ""

    def select(self, *args, **kwargs):
        return self

    def ilike(self, column: str, pattern: str):
        self._term = pattern.strip("%").lower()
        return self

    def execute(self):
        resp = MagicMock()
        resp.data = self._rows_by_term.get(self._term, [])
        return resp


class TriageSupabase:
    def __init__(self, rows_by_term: dict[str, list[dict[str, Any]]]):
        self._rows_by_term = rows_by_term

    def table(self, name: str):
        if name != "symptom_specialty_map":
            raise AssertionError(f"Unexpected table lookup: {name}")
        return SymptomMapQuery(self._rows_by_term)


class SequentialPatientsQuery(FakeQueryBuilder):
    def __init__(self, responses: list[list[dict[str, Any]]]):
        super().__init__([])
        self._responses = responses
        self._execute_count = 0

    def execute(self):
        resp = MagicMock()
        index = min(self._execute_count, len(self._responses) - 1)
        resp.data = self._responses[index]
        self._execute_count += 1
        return resp


def test_identify_patient_rejects_malformed_uin():
    from app.api.vapi_tools.identify_patient import _lookup_patient

    result = _lookup_patient({"uin": "12345"}, {})

    assert result["status"] == "INVALID"
    assert "exactly 9 digits" in result["message"]


@patch("app.api.vapi_tools.identify_patient.get_supabase")
def test_register_patient_phone_collision_does_not_identify_other_patient(mock_get_supabase):
    from app.api.vapi_tools.identify_patient import _register_patient

    fake_sb = FakeSupabase(
        {
            "patients": SequentialPatientsQuery([[], [{"id": str(uuid.uuid4())}]]),
        }
    )
    mock_get_supabase.return_value = fake_sb

    result = _register_patient(
        {
            "uin": "123456789",
            "full_name": "Henry Long",
            "phone": "0423349435",
        },
        {},
    )

    assert result["status"] == "INVALID"
    assert "phone number" in result["message"].lower()
    assert "full_name" not in result
    assert "patient_id" not in result
    assert "uin" not in result


@patch("app.api.vapi_tools.identify_patient.get_supabase")
def test_register_patient_success_message_is_simple(mock_get_supabase):
    from app.api.vapi_tools.identify_patient import _register_patient

    patient_id = str(uuid.uuid4())

    fake_sb = FakeSupabase(
        {
            "patients": SequentialPatientsQuery([[], [], [{"id": patient_id}]]),
        }
    )
    mock_get_supabase.return_value = fake_sb

    result = _register_patient(
        {
            "uin": "123456789",
            "full_name": "Henry Long",
            "phone": "0423349435",
        },
        {},
    )

    assert result["status"] == "REGISTERED"
    assert result["message"] == "You're all set, Henry Long."


@patch("app.api.vapi_tools.identify_patient.get_supabase")
def test_register_patient_accepts_short_digit_phone(mock_get_supabase):
    from app.api.vapi_tools.identify_patient import _register_patient

    patient_id = str(uuid.uuid4())

    fake_sb = FakeSupabase(
        {
            "patients": SequentialPatientsQuery([[], [], [{"id": patient_id}]]),
        }
    )
    mock_get_supabase.return_value = fake_sb

    result = _register_patient(
        {
            "uin": "123456789",
            "full_name": "Henry Long",
            "phone": "123456199",
        },
        {},
    )

    assert result["status"] == "REGISTERED"
    assert result["message"] == "You're all set, Henry Long."


@patch("app.services.triage_engine.get_supabase")
def test_triage_follow_up_answers_refine_specialty(mock_get_supabase):
    from app.api.vapi_tools.triage import _handle_triage

    rows_by_term = {
        "shortness of breath": [
            {
                "symptom": "shortness of breath",
                "specialty_id": "cardiology-id",
                "weight": 1.5,
                "follow_up_questions": ["Does it happen at rest or only during activity?"],
                "specialties": {"id": "cardiology-id", "name": "Cardiology"},
            },
            {
                "symptom": "shortness of breath",
                "specialty_id": "pulmonology-id",
                "weight": 1.5,
                "follow_up_questions": ["Do you smoke or have you smoked in the past?"],
                "specialties": {"id": "pulmonology-id", "name": "Pulmonology"},
            },
        ],
    }
    mock_get_supabase.return_value = TriageSupabase(rows_by_term)

    first_pass = _handle_triage({"symptoms": ["shortness of breath"]}, {})
    refined = _handle_triage(
        {
            "symptoms": ["shortness of breath"],
            "answers": {"Do you smoke or have you smoked in the past?": "yes"},
        },
        {},
    )

    assert first_pass["status"] == "NEED_MORE_INFO"
    assert refined["status"] == "SPECIALTY_FOUND"
    assert refined["specialty_name"] == "Pulmonology"


@patch("app.services.triage_engine.get_supabase")
def test_triage_negative_contraction_answers_are_understood(mock_get_supabase):
    from app.api.vapi_tools.triage import _handle_triage

    rows_by_term = {
        "shortness of breath": [
            {
                "symptom": "shortness of breath",
                "specialty_id": "cardiology-id",
                "weight": 1.5,
                "follow_up_questions": ["Does it happen at rest or only during activity?"],
                "specialties": {"id": "cardiology-id", "name": "Cardiology"},
            },
            {
                "symptom": "shortness of breath",
                "specialty_id": "pulmonology-id",
                "weight": 1.5,
                "follow_up_questions": ["Do you smoke or have you smoked in the past?"],
                "specialties": {"id": "pulmonology-id", "name": "Pulmonology"},
            },
        ],
    }
    mock_get_supabase.return_value = TriageSupabase(rows_by_term)

    refined = _handle_triage(
        {
            "symptoms": ["shortness of breath"],
            "answers": {"Do you smoke or have you smoked in the past?": "I don't"},
        },
        {},
    )

    assert refined["status"] == "SPECIALTY_FOUND"
    assert refined["specialty_name"] == "Cardiology"


@patch("app.api.vapi_tools.book.get_supabase")
@patch("app.api.vapi_tools.book.validate_slot", return_value=None)
def test_book_maps_overlap_constraint_to_taken(mock_validate, mock_get_supabase):
    from app.api.vapi_tools.book import _handle_book

    start = _future(48)
    end = start + timedelta(hours=1)

    fake_sb = FakeSupabase(
        {
            "doctors": FakeQueryBuilder([{"full_name": "Dr. Test"}]),
            "appointments": FakeQueryBuilder(
                raise_on_insert=Exception("violates exclusion constraint no_overlapping_confirmed")
            ),
        }
    )
    mock_get_supabase.return_value = fake_sb

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
    assert "no longer available" in result["message"].lower()


@patch("app.api.vapi_tools.find_slots.find_available_slots")
def test_find_slots_returns_numbered_spoken_choices(mock_find_slots):
    from app.api.vapi_tools.find_slots import _handle_find_slots

    start = _future(48)
    mock_find_slots.return_value = [
        {
            "doctor_id": str(uuid.uuid4()),
            "start_at": _utc_iso(start + timedelta(hours=index)),
            "end_at": _utc_iso(start + timedelta(hours=index + 1)),
            "label": f"Monday at {index + 1} PM",
        }
        for index in range(4)
    ]

    result = _handle_find_slots(
        {
            "doctor_id": str(uuid.uuid4()),
            "preferred_day": "next week",
            "preferred_time": "afternoon",
        },
        {},
    )

    assert result["status"] == "OK"
    assert len(result["slots"]) == 3
    assert [slot["slot_number"] for slot in result["slots"]] == [1, 2, 3]
    assert "option 1" in result["message"].lower()
    assert "option 3" in result["message"].lower()
    assert "option 4" not in result["message"].lower()


@patch("app.api.vapi_tools.reschedule._handle_reschedule_finalize")
def test_reschedule_reuses_selected_slot_for_finalize(mock_finalize):
    from app.api.vapi_tools.reschedule import _handle_reschedule

    mock_finalize.return_value = {"status": "RESCHEDULED", "message": "ok"}
    original_appointment_id = str(uuid.uuid4())

    result = _handle_reschedule(
        {
            "appointment_id": original_appointment_id,
            "patient_id": str(uuid.uuid4()),
            "doctor_id": str(uuid.uuid4()),
            "start_at": _utc_iso(_future(72)),
            "end_at": _utc_iso(_future(73)),
        },
        _make_payload({}),
    )

    assert result["status"] == "RESCHEDULED"
    forwarded_args = mock_finalize.call_args.args[0]
    assert forwarded_args["original_appointment_id"] == original_appointment_id


@patch("app.api.vapi_tools.reschedule.find_slots_for_specialty")
@patch("app.api.vapi_tools.reschedule.get_supabase")
@patch("app.api.vapi_tools.reschedule.now_utc")
def test_reschedule_returns_only_numbered_spoken_choices(mock_now, mock_get_supabase, mock_find_slots):
    from app.api.vapi_tools.reschedule import _handle_reschedule

    now = datetime.now(timezone.utc)
    mock_now.return_value = now

    appointment_id = str(uuid.uuid4())
    start = _future(72)
    mock_find_slots.return_value = [
        {
            "doctor_id": str(uuid.uuid4()),
            "doctor_name": "Dr. Kim",
            "specialty_id": str(uuid.uuid4()),
            "start_at": _utc_iso(start + timedelta(hours=index)),
            "end_at": _utc_iso(start + timedelta(hours=index + 1)),
            "label": f"Monday at {index + 1} PM",
        }
        for index in range(4)
    ]
    mock_get_supabase.return_value = FakeSupabase(
        {
            "appointments": FakeQueryBuilder(
                [
                    {
                        "id": appointment_id,
                        "specialty_id": str(uuid.uuid4()),
                        "doctor_id": str(uuid.uuid4()),
                        "status": "CONFIRMED",
                        "start_at": _utc_iso(_future(48)),
                        "end_at": _utc_iso(_future(49)),
                    }
                ]
            )
        }
    )

    result = _handle_reschedule(
        {
            "appointment_id": appointment_id,
            "preferred_day": "next week",
            "preferred_time": "afternoon",
        },
        _make_payload({}),
    )

    assert result["status"] == "SLOTS_AVAILABLE"
    assert len(result["slots"]) == 3
    assert [slot["slot_number"] for slot in result["slots"]] == [1, 2, 3]
    assert "option 1" in result["message"].lower()
    assert "option 4" not in result["message"].lower()


@patch("app.api.vapi_tools.reschedule.get_supabase")
@patch("app.api.vapi_tools.reschedule.validate_slot", return_value=None)
@patch("app.api.vapi_tools.reschedule.now_utc")
def test_reschedule_finalize_can_infer_patient_id_from_original_appointment(mock_now, mock_validate, mock_get_supabase):
    from app.api.vapi_tools.reschedule import _handle_reschedule

    now = datetime.now(timezone.utc)
    mock_now.return_value = now

    original_appointment_id = str(uuid.uuid4())
    patient_id = str(uuid.uuid4())
    doctor_id = str(uuid.uuid4())
    new_appointment_id = str(uuid.uuid4())
    orig_start = _future(48)
    new_start = _future(72)

    call_count = {"appointments": 0}

    class MultiCallAppointments(FakeQueryBuilder):
        def select(self, *a, **kw):
            call_count["appointments"] += 1
            if call_count["appointments"] == 1:
                self._data = [
                    {
                        "id": original_appointment_id,
                        "patient_id": patient_id,
                        "status": "CONFIRMED",
                        "start_at": _utc_iso(orig_start),
                        "end_at": _utc_iso(orig_start + timedelta(hours=1)),
                        "specialty_id": None,
                        "reason": "checkup",
                        "symptoms": None,
                        "severity_description": None,
                        "severity_rating": None,
                        "urgency": "ROUTINE",
                    }
                ]
            return self

        def insert(self, row):
            self._data = [{"id": new_appointment_id, **row}]
            self._last_inserted = row
            return self

        def update(self, data):
            self._data = [{"id": original_appointment_id}]
            return self

    fake_appointments = MultiCallAppointments()
    mock_get_supabase.return_value = FakeSupabase(
        {
            "appointments": fake_appointments,
            "doctors": FakeQueryBuilder([{"full_name": "Dr. Test"}]),
        }
    )

    result = _handle_reschedule(
        {
            "appointment_id": original_appointment_id,
            "doctor_id": doctor_id,
            "start_at": _utc_iso(new_start),
            "end_at": _utc_iso(new_start + timedelta(hours=1)),
        },
        _make_payload({}),
    )

    assert result["status"] == "RESCHEDULED"
    assert fake_appointments._last_inserted["patient_id"] == patient_id


@patch("app.api.vapi_tools.reschedule.get_supabase")
@patch("app.api.vapi_tools.reschedule.now_utc")
def test_find_appointment_multiple_returns_numbered_voice_options(mock_now, mock_get_supabase):
    from app.api.vapi_tools.reschedule import _handle_find_appointment

    now = datetime.now(timezone.utc)
    mock_now.return_value = now
    first_start = _future(48)
    second_start = _future(72)

    mock_get_supabase.return_value = FakeSupabase(
        {
            "appointments": FakeQueryBuilder(
                [
                    {
                        "id": str(uuid.uuid4()),
                        "doctor_id": str(uuid.uuid4()),
                        "specialty_id": None,
                        "start_at": _utc_iso(first_start),
                        "end_at": _utc_iso(first_start + timedelta(hours=1)),
                        "reason": "diarrhea",
                        "symptoms": None,
                        "status": "CONFIRMED",
                        "doctors": {"full_name": "Robert Kim"},
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "doctor_id": str(uuid.uuid4()),
                        "specialty_id": None,
                        "start_at": _utc_iso(second_start),
                        "end_at": _utc_iso(second_start + timedelta(hours=1)),
                        "reason": "trouble sleeping",
                        "symptoms": None,
                        "status": "CONFIRMED",
                        "doctors": {"full_name": "Ava Patel"},
                    },
                ]
            )
        }
    )

    result = _handle_find_appointment(
        {"patient_id": str(uuid.uuid4())},
        _make_payload({}),
    )

    assert result["status"] == "MULTIPLE"
    assert [item["appointment_number"] for item in result["appointments"]] == [1, 2]
    assert "option 1" in result["message"].lower()
    assert "option 2" in result["message"].lower()
    assert "robert kim" in result["message"].lower()
    assert "ava patel" in result["message"].lower()
