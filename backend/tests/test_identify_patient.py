"""Tests for identify_patient and register_patient tool handlers."""
from __future__ import annotations

import uuid
from unittest.mock import patch

from tests.conftest import FakeQueryBuilder, FakeSupabase, SequentialQueryBuilder


class TestIdentifyPatient:
    def test_missing_uin(self):
        from app.api.vapi_tools.identify_patient import _lookup_patient
        result = _lookup_patient({}, {})
        assert result["status"] == "INVALID"

    def test_uin_too_short(self):
        from app.api.vapi_tools.identify_patient import _lookup_patient
        result = _lookup_patient({"uin": "12345"}, {})
        assert result["status"] == "INVALID"
        assert "9 digits" in result["message"]

    def test_uin_too_long(self):
        from app.api.vapi_tools.identify_patient import _lookup_patient
        result = _lookup_patient({"uin": "1234567890"}, {})
        assert result["status"] == "INVALID"

    def test_spoken_word_digits_converted(self):
        from app.api.vapi_tools.identify_patient import _normalize_uin
        assert _normalize_uin("one two three four five six seven eight nine") == "123456789"

    def test_oh_and_o_convert_to_zero(self):
        from app.api.vapi_tools.identify_patient import _normalize_uin
        assert _normalize_uin("oh one two oh four five six seven eight") == "012045678"
        assert _normalize_uin("o one two o four five six seven eight") == "012045678"

    def test_mixed_digits_and_words(self):
        from app.api.vapi_tools.identify_patient import _normalize_uin
        assert _normalize_uin("1 two 3 four 5 six 7 eight 9") == "123456789"

    @patch("app.api.vapi_tools.identify_patient.get_supabase")
    def test_patient_found(self, mock_sb):
        from app.api.vapi_tools.identify_patient import _lookup_patient
        pid = str(uuid.uuid4())
        mock_sb.return_value = FakeSupabase({
            "patients": FakeQueryBuilder([{
                "id": pid, "uin": "111222333",
                "full_name": "Jane Doe", "phone": "5551234567",
                "email": None, "allergies": None,
            }]),
        })
        result = _lookup_patient({"uin": "111222333"}, {})
        assert result["status"] == "FOUND"
        assert result["patient_id"] == pid
        assert result["full_name"] == "Jane Doe"

    @patch("app.api.vapi_tools.identify_patient.get_supabase")
    def test_patient_not_found(self, mock_sb):
        from app.api.vapi_tools.identify_patient import _lookup_patient
        mock_sb.return_value = FakeSupabase({"patients": FakeQueryBuilder([])})
        result = _lookup_patient({"uin": "999888777"}, {})
        assert result["status"] == "NOT_FOUND"


class TestRegisterPatient:
    def test_missing_uin(self):
        from app.api.vapi_tools.identify_patient import _register_patient
        result = _register_patient({"full_name": "X", "phone": "123"}, {})
        assert result["status"] == "INVALID"

    def test_missing_name(self):
        from app.api.vapi_tools.identify_patient import _register_patient
        result = _register_patient({"uin": "123456789", "phone": "123"}, {})
        assert result["status"] == "INVALID"

    def test_missing_phone(self):
        from app.api.vapi_tools.identify_patient import _register_patient
        result = _register_patient({"uin": "123456789", "full_name": "X"}, {})
        assert result["status"] == "INVALID"

    @patch("app.api.vapi_tools.identify_patient.get_supabase")
    def test_already_exists(self, mock_sb):
        from app.api.vapi_tools.identify_patient import _register_patient
        pid = str(uuid.uuid4())
        mock_sb.return_value = FakeSupabase({
            "patients": FakeQueryBuilder([{"id": pid, "uin": "123456789", "full_name": "Existing"}]),
        })
        result = _register_patient({"uin": "123456789", "full_name": "X", "phone": "123"}, {})
        assert result["status"] == "ALREADY_EXISTS"
        assert result["patient_id"] == pid

    @patch("app.api.vapi_tools.identify_patient.get_supabase")
    def test_phone_collision_no_leak(self, mock_sb):
        from app.api.vapi_tools.identify_patient import _register_patient
        mock_sb.return_value = FakeSupabase({
            "patients": SequentialQueryBuilder([
                [],
                [{"id": str(uuid.uuid4())}],
            ]),
        })
        result = _register_patient({"uin": "123456789", "full_name": "X", "phone": "5551234567"}, {})
        assert result["status"] == "INVALID"
        assert "phone number" in result["message"].lower()
        assert "patient_id" not in result
        assert "full_name" not in result

    @patch("app.api.vapi_tools.identify_patient.get_supabase")
    def test_successful_registration(self, mock_sb):
        from app.api.vapi_tools.identify_patient import _register_patient
        pid = str(uuid.uuid4())
        mock_sb.return_value = FakeSupabase({
            "patients": SequentialQueryBuilder([
                [],
                [],
                [{"id": pid, "uin": "123456789", "full_name": "Henry Long"}],
            ]),
        })
        result = _register_patient(
            {"uin": "123456789", "full_name": "Henry Long", "phone": "5551234567"}, {},
        )
        assert result["status"] == "REGISTERED"
        assert result["full_name"] == "Henry Long"

    @patch("app.api.vapi_tools.identify_patient.get_supabase")
    def test_registration_with_optional_fields(self, mock_sb):
        from app.api.vapi_tools.identify_patient import _register_patient
        mock_sb.return_value = FakeSupabase({
            "patients": SequentialQueryBuilder([
                [],
                [],
                [{"id": str(uuid.uuid4()), "uin": "123456789", "full_name": "X"}],
            ]),
        })
        result = _register_patient(
            {"uin": "123456789", "full_name": "X", "phone": "123",
             "email": "x@test.com", "allergies": "peanuts"}, {},
        )
        assert result["status"] == "REGISTERED"
