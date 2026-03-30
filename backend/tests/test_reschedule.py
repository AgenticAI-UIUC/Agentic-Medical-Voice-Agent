"""Tests for find_appointment, reschedule, and reschedule_finalize tool handlers."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from tests.conftest import FakeQueryBuilder, FakeSupabase, future, utc_iso, make_payload


# ===================================================================
# FIND APPOINTMENT
# ===================================================================

class TestFindAppointment:
    def test_missing_patient_id(self):
        from app.api.vapi_tools.reschedule import _handle_find_appointment
        result = _handle_find_appointment({}, make_payload())
        assert result["status"] == "INVALID"

    @patch("app.api.vapi_tools.reschedule.get_supabase")
    @patch("app.api.vapi_tools.reschedule.now_utc")
    def test_no_appointments(self, mock_now, mock_sb):
        from app.api.vapi_tools.reschedule import _handle_find_appointment
        mock_now.return_value = datetime.now(timezone.utc)
        mock_sb.return_value = FakeSupabase({"appointments": FakeQueryBuilder([])})
        result = _handle_find_appointment({"patient_id": str(uuid.uuid4())}, make_payload())
        assert result["status"] == "NO_APPOINTMENTS"

    @patch("app.api.vapi_tools.reschedule.get_supabase")
    @patch("app.api.vapi_tools.reschedule.now_utc")
    def test_single_appointment_found(self, mock_now, mock_sb):
        from app.api.vapi_tools.reschedule import _handle_find_appointment
        mock_now.return_value = datetime.now(timezone.utc)
        start = future(48)
        appt_id = str(uuid.uuid4())
        mock_sb.return_value = FakeSupabase({
            "appointments": FakeQueryBuilder([{
                "id": appt_id, "doctor_id": str(uuid.uuid4()),
                "specialty_id": None,
                "start_at": utc_iso(start), "end_at": utc_iso(start + timedelta(hours=1)),
                "reason": "headache", "symptoms": None, "status": "CONFIRMED",
                "doctors": {"full_name": "Dr. Lee"},
            }]),
        })
        result = _handle_find_appointment({"patient_id": str(uuid.uuid4())}, make_payload())
        assert result["status"] == "FOUND"
        assert result["appointment"]["id"] == appt_id

    @patch("app.api.vapi_tools.reschedule.get_supabase")
    @patch("app.api.vapi_tools.reschedule.now_utc")
    def test_multiple_appointments(self, mock_now, mock_sb):
        from app.api.vapi_tools.reschedule import _handle_find_appointment
        mock_now.return_value = datetime.now(timezone.utc)
        s1, s2 = future(48), future(72)
        mock_sb.return_value = FakeSupabase({
            "appointments": FakeQueryBuilder([
                {"id": str(uuid.uuid4()), "doctor_id": str(uuid.uuid4()),
                 "specialty_id": None, "start_at": utc_iso(s1),
                 "end_at": utc_iso(s1 + timedelta(hours=1)),
                 "reason": "cough", "symptoms": None, "status": "CONFIRMED",
                 "doctors": {"full_name": "Dr. A"}},
                {"id": str(uuid.uuid4()), "doctor_id": str(uuid.uuid4()),
                 "specialty_id": None, "start_at": utc_iso(s2),
                 "end_at": utc_iso(s2 + timedelta(hours=1)),
                 "reason": "rash", "symptoms": None, "status": "CONFIRMED",
                 "doctors": {"full_name": "Dr. B"}},
            ]),
        })
        result = _handle_find_appointment({"patient_id": str(uuid.uuid4())}, make_payload())
        assert result["status"] == "MULTIPLE"
        assert len(result["appointments"]) == 2

    @patch("app.api.vapi_tools.reschedule.get_supabase")
    @patch("app.api.vapi_tools.reschedule.now_utc")
    def test_filter_by_doctor_name(self, mock_now, mock_sb):
        from app.api.vapi_tools.reschedule import _handle_find_appointment
        mock_now.return_value = datetime.now(timezone.utc)
        s1, s2 = future(48), future(72)
        target_id = str(uuid.uuid4())
        mock_sb.return_value = FakeSupabase({
            "appointments": FakeQueryBuilder([
                {"id": str(uuid.uuid4()), "doctor_id": str(uuid.uuid4()),
                 "specialty_id": None, "start_at": utc_iso(s1),
                 "end_at": utc_iso(s1 + timedelta(hours=1)),
                 "reason": "cough", "symptoms": None, "status": "CONFIRMED",
                 "doctors": {"full_name": "Dr. Alpha"}},
                {"id": target_id, "doctor_id": str(uuid.uuid4()),
                 "specialty_id": None, "start_at": utc_iso(s2),
                 "end_at": utc_iso(s2 + timedelta(hours=1)),
                 "reason": "rash", "symptoms": None, "status": "CONFIRMED",
                 "doctors": {"full_name": "Dr. Beta"}},
            ]),
        })
        result = _handle_find_appointment(
            {"patient_id": str(uuid.uuid4()), "doctor_name": "Beta"}, make_payload(),
        )
        assert result["status"] == "FOUND"
        assert result["appointment"]["id"] == target_id


# ===================================================================
# RESCHEDULE (slot discovery)
# ===================================================================

class TestReschedule:
    def test_missing_appointment_id(self):
        from app.api.vapi_tools.reschedule import _handle_reschedule
        result = _handle_reschedule({}, make_payload())
        assert result["status"] == "INVALID"

    @patch("app.api.vapi_tools.reschedule.get_supabase")
    @patch("app.api.vapi_tools.reschedule.now_utc")
    def test_appointment_not_found(self, mock_now, mock_sb):
        from app.api.vapi_tools.reschedule import _handle_reschedule
        mock_now.return_value = datetime.now(timezone.utc)
        mock_sb.return_value = FakeSupabase({"appointments": FakeQueryBuilder([])})
        result = _handle_reschedule({"appointment_id": str(uuid.uuid4())}, make_payload())
        assert result["status"] == "NOT_FOUND"

    @patch("app.api.vapi_tools.reschedule.get_supabase")
    @patch("app.api.vapi_tools.reschedule.now_utc")
    def test_cancelled_appointment_rejected(self, mock_now, mock_sb):
        from app.api.vapi_tools.reschedule import _handle_reschedule
        mock_now.return_value = datetime.now(timezone.utc)
        mock_sb.return_value = FakeSupabase({
            "appointments": FakeQueryBuilder([{
                "id": str(uuid.uuid4()), "specialty_id": None,
                "doctor_id": str(uuid.uuid4()), "status": "CANCELLED",
                "start_at": utc_iso(future(48)), "end_at": utc_iso(future(49)),
            }]),
        })
        result = _handle_reschedule({"appointment_id": str(uuid.uuid4())}, make_payload())
        assert result["status"] == "INVALID"

    @patch("app.api.vapi_tools.reschedule.get_supabase")
    @patch("app.api.vapi_tools.reschedule.now_utc")
    def test_past_appointment_rejected(self, mock_now, mock_sb):
        from app.api.vapi_tools.reschedule import _handle_reschedule
        now = datetime.now(timezone.utc)
        mock_now.return_value = now
        past = now - timedelta(hours=2)
        mock_sb.return_value = FakeSupabase({
            "appointments": FakeQueryBuilder([{
                "id": str(uuid.uuid4()), "specialty_id": None,
                "doctor_id": str(uuid.uuid4()), "status": "CONFIRMED",
                "start_at": utc_iso(past), "end_at": utc_iso(past + timedelta(hours=1)),
            }]),
        })
        result = _handle_reschedule({"appointment_id": str(uuid.uuid4())}, make_payload())
        assert result["status"] == "INVALID"
        assert "past" in result["message"].lower()

    @patch("app.api.vapi_tools.reschedule.find_available_slots")
    @patch("app.api.vapi_tools.reschedule.get_supabase")
    @patch("app.api.vapi_tools.reschedule.now_utc")
    def test_no_slots_available(self, mock_now, mock_sb, mock_find):
        from app.api.vapi_tools.reschedule import _handle_reschedule
        mock_now.return_value = datetime.now(timezone.utc)
        mock_find.return_value = []
        mock_sb.return_value = FakeSupabase({
            "appointments": FakeQueryBuilder([{
                "id": str(uuid.uuid4()), "specialty_id": None,
                "doctor_id": str(uuid.uuid4()), "status": "CONFIRMED",
                "start_at": utc_iso(future(48)), "end_at": utc_iso(future(49)),
            }]),
        })
        result = _handle_reschedule(
            {"appointment_id": str(uuid.uuid4()), "preferred_day": "next week", "preferred_time": "morning"},
            make_payload(),
        )
        assert result["status"] == "NO_SLOTS"

    @patch("app.api.vapi_tools.reschedule.find_slots_for_specialty")
    @patch("app.api.vapi_tools.reschedule.get_supabase")
    @patch("app.api.vapi_tools.reschedule.now_utc")
    def test_slots_available_with_specialty(self, mock_now, mock_sb, mock_find):
        from app.api.vapi_tools.reschedule import _handle_reschedule
        mock_now.return_value = datetime.now(timezone.utc)
        spec_id = str(uuid.uuid4())
        start = future(72)
        mock_find.return_value = [
            {"doctor_id": str(uuid.uuid4()), "doctor_name": "Dr. Kim",
             "start_at": utc_iso(start), "end_at": utc_iso(start + timedelta(hours=1)),
             "label": "Wednesday at 2 PM"},
        ]
        mock_sb.return_value = FakeSupabase({
            "appointments": FakeQueryBuilder([{
                "id": str(uuid.uuid4()), "specialty_id": spec_id,
                "doctor_id": str(uuid.uuid4()), "status": "CONFIRMED",
                "start_at": utc_iso(future(48)), "end_at": utc_iso(future(49)),
            }]),
        })
        result = _handle_reschedule(
            {"appointment_id": str(uuid.uuid4()), "preferred_day": "next week"}, make_payload(),
        )
        assert result["status"] == "SLOTS_AVAILABLE"
        assert len(result["slots"]) == 1

    @patch("app.api.vapi_tools.reschedule._handle_reschedule_finalize")
    def test_slot_number_triggers_finalize_from_cache(self, mock_finalize):
        """When slot_number is passed and cached, should forward to finalize."""
        from app.api.vapi_tools.reschedule import _handle_reschedule, _cache_slots

        mock_finalize.return_value = {"status": "RESCHEDULED", "message": "ok"}
        call_id = f"call-sn-{uuid.uuid4()}"
        appt_id = str(uuid.uuid4())
        doc_id = str(uuid.uuid4())
        start = future(72)

        _cache_slots(call_id, appt_id, [
            {"slot_number": 1, "doctor_id": doc_id,
             "start_at": utc_iso(start), "end_at": utc_iso(start + timedelta(hours=1)),
             "label": "Monday at 3 PM"},
        ])

        result = _handle_reschedule(
            {"appointment_id": appt_id, "slot_number": 1},
            make_payload(call_id=call_id),
        )
        assert result["status"] == "RESCHEDULED"
        forwarded = mock_finalize.call_args.args[0]
        assert forwarded["doctor_id"] == doc_id
        assert forwarded["original_appointment_id"] == appt_id


# ===================================================================
# RESCHEDULE FINALIZE
# ===================================================================

class TestRescheduleFinalize:
    def test_missing_required_fields(self):
        from app.api.vapi_tools.reschedule import _handle_reschedule_finalize
        result = _handle_reschedule_finalize(
            {"original_appointment_id": str(uuid.uuid4())}, make_payload(),
        )
        assert result["status"] == "INVALID"

    def test_invalid_times(self):
        from app.api.vapi_tools.reschedule import _handle_reschedule_finalize
        result = _handle_reschedule_finalize(
            {"original_appointment_id": str(uuid.uuid4()), "doctor_id": str(uuid.uuid4()),
             "start_at": "bad", "end_at": "bad"},
            make_payload(),
        )
        assert result["status"] == "INVALID"

    def test_end_before_start(self):
        from app.api.vapi_tools.reschedule import _handle_reschedule_finalize
        start = future(48)
        result = _handle_reschedule_finalize(
            {"original_appointment_id": str(uuid.uuid4()), "doctor_id": str(uuid.uuid4()),
             "start_at": utc_iso(start), "end_at": utc_iso(start - timedelta(hours=1))},
            make_payload(),
        )
        assert result["status"] == "INVALID"

    @patch("app.api.vapi_tools.reschedule.get_supabase")
    @patch("app.api.vapi_tools.reschedule.validate_slot", return_value=None)
    @patch("app.api.vapi_tools.reschedule.now_utc")
    def test_successful_reschedule(self, mock_now, _mock_validate, mock_sb):
        from app.api.vapi_tools.reschedule import _handle_reschedule_finalize
        now = datetime.now(timezone.utc)
        mock_now.return_value = now
        orig_start = future(48)
        new_start = future(72)
        orig_id = str(uuid.uuid4())
        new_id = str(uuid.uuid4())

        call_count = {"sel": 0}

        class Multi(FakeQueryBuilder):
            def select(self, *_a, **_kw):
                call_count["sel"] += 1
                if call_count["sel"] == 1:
                    self._data = [{
                        "id": orig_id, "patient_id": str(uuid.uuid4()),
                        "status": "CONFIRMED",
                        "start_at": utc_iso(orig_start),
                        "end_at": utc_iso(orig_start + timedelta(hours=1)),
                        "specialty_id": None, "reason": "test",
                        "symptoms": None, "severity_description": None,
                        "severity_rating": None, "urgency": "ROUTINE",
                    }]
                return self

            def insert(self, row):
                self._data = [{"id": new_id, **row}]
                return self

            def update(self, _data):
                self._data = [{"id": orig_id}]
                return self

        mock_sb.return_value = FakeSupabase({
            "appointments": Multi(),
            "doctors": FakeQueryBuilder([{"full_name": "Dr. Test"}]),
        })
        result = _handle_reschedule_finalize(
            {"original_appointment_id": orig_id, "doctor_id": str(uuid.uuid4()),
             "start_at": utc_iso(new_start), "end_at": utc_iso(new_start + timedelta(hours=1))},
            make_payload(),
        )
        assert result["status"] == "RESCHEDULED"
        assert result["new_appointment_id"] == new_id
        assert result["cancelled_appointment_id"] == orig_id

    @patch("app.api.vapi_tools.reschedule._check_overlap", return_value=True)
    @patch("app.api.vapi_tools.reschedule.get_supabase")
    @patch("app.api.vapi_tools.reschedule.validate_slot")
    @patch("app.api.vapi_tools.reschedule.now_utc")
    def test_taken_slot_does_not_cancel_original(self, mock_now, mock_validate, mock_sb, _mock_overlap):
        from app.api.vapi_tools.reschedule import _handle_reschedule_finalize
        mock_now.return_value = datetime.now(timezone.utc)
        orig_start = future(48)
        new_start = future(72)
        orig_id = str(uuid.uuid4())
        mock_validate.return_value = {"status": "TAKEN", "message": "Taken."}
        mock_sb.return_value = FakeSupabase({
            "appointments": FakeQueryBuilder([{
                "id": orig_id, "patient_id": str(uuid.uuid4()),
                "status": "CONFIRMED",
                "start_at": utc_iso(orig_start),
                "end_at": utc_iso(orig_start + timedelta(hours=1)),
                "specialty_id": None, "reason": None, "symptoms": None,
                "severity_description": None, "severity_rating": None, "urgency": "ROUTINE",
            }]),
        })
        result = _handle_reschedule_finalize(
            {"original_appointment_id": orig_id, "doctor_id": str(uuid.uuid4()),
             "start_at": utc_iso(new_start), "end_at": utc_iso(new_start + timedelta(hours=1))},
            make_payload(),
        )
        assert result["status"] == "TAKEN"

    @patch("app.api.vapi_tools.reschedule.get_supabase")
    @patch("app.api.vapi_tools.reschedule.now_utc")
    def test_past_original_appointment_rejected(self, mock_now, mock_sb):
        from app.api.vapi_tools.reschedule import _handle_reschedule_finalize
        now = datetime.now(timezone.utc)
        mock_now.return_value = now
        past = now - timedelta(hours=2)
        new_start = future(72)
        orig_id = str(uuid.uuid4())
        mock_sb.return_value = FakeSupabase({
            "appointments": FakeQueryBuilder([{
                "id": orig_id, "patient_id": str(uuid.uuid4()),
                "status": "CONFIRMED",
                "start_at": utc_iso(past),
                "end_at": utc_iso(past + timedelta(hours=1)),
                "specialty_id": None, "reason": None, "symptoms": None,
                "severity_description": None, "severity_rating": None, "urgency": "ROUTINE",
            }]),
        })
        result = _handle_reschedule_finalize(
            {"original_appointment_id": orig_id, "doctor_id": str(uuid.uuid4()),
             "start_at": utc_iso(new_start), "end_at": utc_iso(new_start + timedelta(hours=1))},
            make_payload(),
        )
        assert result["status"] == "INVALID"
        assert "past" in result["message"].lower()
