"""Tests for cancel tool handler."""
from __future__ import annotations

import uuid
from unittest.mock import patch

from tests.conftest import FakeQueryBuilder, FakeSupabase


class TestCancel:
    def test_missing_appointment_id(self):
        from app.api.vapi_tools.cancel import _handle_cancel
        result = _handle_cancel({}, {})
        assert result["status"] == "INVALID"

    @patch("app.api.vapi_tools.cancel.get_supabase")
    def test_appointment_not_found(self, mock_sb):
        from app.api.vapi_tools.cancel import _handle_cancel
        mock_sb.return_value = FakeSupabase({"appointments": FakeQueryBuilder([])})
        result = _handle_cancel({"appointment_id": str(uuid.uuid4())}, {})
        assert result["status"] == "NOT_FOUND"

    @patch("app.api.vapi_tools.cancel.get_supabase")
    def test_already_cancelled(self, mock_sb):
        from app.api.vapi_tools.cancel import _handle_cancel
        mock_sb.return_value = FakeSupabase({
            "appointments": FakeQueryBuilder([{
                "id": str(uuid.uuid4()), "status": "CANCELLED",
                "doctors": {"full_name": "Dr. X"},
            }]),
        })
        result = _handle_cancel({"appointment_id": str(uuid.uuid4())}, {})
        assert result["status"] == "INVALID"
        assert "already cancelled" in result["message"].lower()

    @patch("app.api.vapi_tools.cancel.get_supabase")
    def test_successful_cancellation(self, mock_sb):
        from app.api.vapi_tools.cancel import _handle_cancel
        appt_id = str(uuid.uuid4())
        mock_sb.return_value = FakeSupabase({
            "appointments": FakeQueryBuilder([{
                "id": appt_id, "status": "CONFIRMED",
                "doctors": {"full_name": "Dr. Cancel"},
            }]),
        })
        result = _handle_cancel({"appointment_id": appt_id}, {})
        assert result["status"] == "CANCELLED"
        assert "Dr. Cancel" in result["message"]

    @patch("app.api.vapi_tools.cancel.get_supabase")
    def test_missing_doctor_name_fallback(self, mock_sb):
        from app.api.vapi_tools.cancel import _handle_cancel
        mock_sb.return_value = FakeSupabase({
            "appointments": FakeQueryBuilder([{
                "id": str(uuid.uuid4()), "status": "CONFIRMED",
                "doctors": {},
            }]),
        })
        result = _handle_cancel({"appointment_id": str(uuid.uuid4())}, {})
        assert result["status"] == "CANCELLED"
        assert "your doctor" in result["message"]
