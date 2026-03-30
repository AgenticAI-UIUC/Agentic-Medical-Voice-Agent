"""Tests for book tool handler."""
from __future__ import annotations

import uuid
from datetime import timedelta
from unittest.mock import patch

from tests.conftest import FakeQueryBuilder, FakeSupabase, future, utc_iso, make_payload


class TestBook:
    def test_missing_required_fields(self):
        from app.api.vapi_tools.book import _handle_book
        result = _handle_book({"patient_id": str(uuid.uuid4())}, make_payload())
        assert result["status"] == "INVALID"

    def test_invalid_datetime_strings(self):
        from app.api.vapi_tools.book import _handle_book
        result = _handle_book(
            {"patient_id": str(uuid.uuid4()), "doctor_id": str(uuid.uuid4()),
             "start_at": "not-a-date", "end_at": "also-not-a-date"},
            make_payload(),
        )
        assert result["status"] == "INVALID"

    def test_end_before_start(self):
        from app.api.vapi_tools.book import _handle_book
        start = future(48)
        result = _handle_book(
            {"patient_id": str(uuid.uuid4()), "doctor_id": str(uuid.uuid4()),
             "start_at": utc_iso(start), "end_at": utc_iso(start - timedelta(hours=1))},
            make_payload(),
        )
        assert result["status"] == "INVALID"

    @patch("app.api.vapi_tools.book.get_supabase")
    @patch("app.api.vapi_tools.book.validate_slot", return_value=None)
    def test_successful_booking(self, _mock_validate, mock_sb):
        from app.api.vapi_tools.book import _handle_book
        start = future(48)
        mock_sb.return_value = FakeSupabase({
            "doctors": FakeQueryBuilder([{"full_name": "Dr. Smith"}]),
            "appointments": FakeQueryBuilder(),
        })
        result = _handle_book(
            {"patient_id": str(uuid.uuid4()), "doctor_id": str(uuid.uuid4()),
             "start_at": utc_iso(start), "end_at": utc_iso(start + timedelta(hours=1))},
            make_payload(),
        )
        assert result["status"] == "CONFIRMED"
        assert "appointment_id" in result
        assert "Dr. Smith" in result["message"]

    @patch("app.api.vapi_tools.book.validate_slot")
    def test_slot_validation_rejection(self, mock_validate):
        from app.api.vapi_tools.book import _handle_book
        mock_validate.return_value = {"status": "TAKEN", "message": "Slot taken."}
        start = future(48)
        result = _handle_book(
            {"patient_id": str(uuid.uuid4()), "doctor_id": str(uuid.uuid4()),
             "start_at": utc_iso(start), "end_at": utc_iso(start + timedelta(hours=1))},
            make_payload(),
        )
        assert result["status"] == "TAKEN"

    @patch("app.api.vapi_tools.book.get_supabase")
    @patch("app.api.vapi_tools.book.validate_slot", return_value=None)
    def test_db_constraint_violation_maps_to_taken(self, _mock_validate, mock_sb):
        from app.api.vapi_tools.book import _handle_book
        start = future(48)
        mock_sb.return_value = FakeSupabase({
            "doctors": FakeQueryBuilder([{"full_name": "Dr. Test"}]),
            "appointments": FakeQueryBuilder(
                raise_on_insert=Exception("no_overlapping_confirmed constraint")
            ),
        })
        result = _handle_book(
            {"patient_id": str(uuid.uuid4()), "doctor_id": str(uuid.uuid4()),
             "start_at": utc_iso(start), "end_at": utc_iso(start + timedelta(hours=1))},
            make_payload(),
        )
        assert result["status"] == "TAKEN"

    @patch("app.api.vapi_tools.book.pop_cached_slot")
    @patch("app.api.vapi_tools.book.get_supabase")
    @patch("app.api.vapi_tools.book.validate_slot", return_value=None)
    def test_slot_number_resolves_from_cache(self, _mock_validate, mock_sb, mock_pop):
        from app.api.vapi_tools.book import _handle_book
        doc_id = str(uuid.uuid4())
        start = future(48)

        mock_pop.return_value = {
            "doctor_id": doc_id,
            "start_at": utc_iso(start),
            "end_at": utc_iso(start + timedelta(hours=1)),
        }
        mock_sb.return_value = FakeSupabase({
            "doctors": FakeQueryBuilder([{"full_name": "Dr. Cached"}]),
            "appointments": FakeQueryBuilder([{"id": str(uuid.uuid4())}]),
        })

        result = _handle_book(
            {"patient_id": str(uuid.uuid4()), "slot_number": 2},
            make_payload(),
        )
        assert result["status"] == "CONFIRMED"
        mock_pop.assert_called_once()
