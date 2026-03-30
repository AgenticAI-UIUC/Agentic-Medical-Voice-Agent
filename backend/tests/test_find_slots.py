"""Tests for find_slots tool handler and slot caching."""
from __future__ import annotations

import uuid
from datetime import timedelta
from unittest.mock import patch

from tests.conftest import future, utc_iso, make_payload


class TestFindSlots:
    def test_missing_specialty_and_doctor(self):
        from app.api.vapi_tools.find_slots import _handle_find_slots
        result = _handle_find_slots({}, make_payload())
        assert result["status"] == "INVALID"

    @patch("app.api.vapi_tools.find_slots.find_available_slots")
    def test_no_slots_for_doctor(self, mock_find):
        from app.api.vapi_tools.find_slots import _handle_find_slots
        mock_find.return_value = []
        result = _handle_find_slots(
            {"doctor_id": str(uuid.uuid4()), "preferred_day": "tomorrow", "preferred_time": "morning"},
            make_payload(),
        )
        assert result["status"] == "NO_SLOTS"

    @patch("app.api.vapi_tools.find_slots.find_available_slots")
    def test_slots_found_by_doctor(self, mock_find):
        from app.api.vapi_tools.find_slots import _handle_find_slots
        start = future(48)
        mock_find.return_value = [
            {"start_at": utc_iso(start), "end_at": utc_iso(start + timedelta(hours=1)),
             "label": "Monday at 2 PM"},
        ]
        result = _handle_find_slots(
            {"doctor_id": str(uuid.uuid4()), "preferred_day": "next week", "preferred_time": "afternoon"},
            make_payload(),
        )
        assert result["status"] == "OK"
        assert len(result["slots"]) == 1
        assert result["slots"][0]["slot_number"] == 1

    @patch("app.api.vapi_tools.find_slots.find_slots_for_specialty")
    def test_no_slots_for_specialty(self, mock_find):
        from app.api.vapi_tools.find_slots import _handle_find_slots
        mock_find.return_value = []
        result = _handle_find_slots(
            {"specialty_id": str(uuid.uuid4()), "preferred_day": "tomorrow", "preferred_time": "any"},
            make_payload(),
        )
        assert result["status"] == "NO_SLOTS"

    @patch("app.api.vapi_tools.find_slots.find_slots_for_specialty")
    def test_slots_capped_at_three(self, mock_find):
        from app.api.vapi_tools.find_slots import _handle_find_slots
        start = future(48)
        mock_find.return_value = [
            {"doctor_id": str(uuid.uuid4()), "doctor_name": f"Dr. {i}",
             "start_at": utc_iso(start + timedelta(hours=i)),
             "end_at": utc_iso(start + timedelta(hours=i + 1)),
             "label": f"Slot {i}"}
            for i in range(5)
        ]
        result = _handle_find_slots({"specialty_id": str(uuid.uuid4())}, make_payload())
        assert result["status"] == "OK"
        assert len(result["slots"]) == 3
        assert [s["slot_number"] for s in result["slots"]] == [1, 2, 3]

    @patch("app.api.vapi_tools.find_slots.find_available_slots")
    def test_slots_cached_for_book(self, mock_find):
        """After find_slots, pop_cached_slot should return the slot data."""
        from app.api.vapi_tools.find_slots import _handle_find_slots, pop_cached_slot

        start = future(48)
        doc_id = str(uuid.uuid4())
        mock_find.return_value = [
            {"doctor_id": doc_id, "start_at": utc_iso(start),
             "end_at": utc_iso(start + timedelta(hours=1)), "label": "Monday at 2 PM"},
        ]
        call_id = f"call-cache-{uuid.uuid4()}"
        _handle_find_slots(
            {"doctor_id": doc_id, "preferred_day": "next week", "preferred_time": "afternoon"},
            make_payload(call_id=call_id),
        )
        cached = pop_cached_slot(call_id, 1)
        assert cached is not None
        assert cached["doctor_id"] == doc_id

    def test_cache_miss_returns_none(self):
        from app.api.vapi_tools.find_slots import pop_cached_slot
        assert pop_cached_slot("nonexistent-call-id", 1) is None
