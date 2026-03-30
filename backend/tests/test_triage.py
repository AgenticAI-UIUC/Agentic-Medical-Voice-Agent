"""Tests for triage and list_specialties tool handlers."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from tests.conftest import FakeQueryBuilder, FakeSupabase


class TestTriage:
    def test_empty_symptoms(self):
        from app.api.vapi_tools.triage import _handle_triage
        result = _handle_triage({"symptoms": []}, {})
        assert result["status"] == "NEED_MORE_INFO"
        assert result["follow_up_questions"]

    def test_string_symptoms_split(self):
        """Comma-separated string is split into a list."""
        from app.api.vapi_tools.triage import _handle_triage

        with patch("app.services.triage_engine.get_supabase") as mock_sb:
            spec_id = str(uuid.uuid4())

            class SymptomQuery:
                def select(self, *_a, **_kw): return self
                def ilike(self, _col, pat):
                    self._data = [{
                        "symptom": pat.strip("%"),
                        "specialty_id": spec_id,
                        "weight": 5.0,
                        "follow_up_questions": [],
                        "specialties": {"id": spec_id, "name": "Gastro"},
                    }]
                    return self
                def execute(self):
                    resp = MagicMock()
                    resp.data = getattr(self, "_data", [])
                    return resp

            class MySb:
                def table(self, _name): return SymptomQuery()

            mock_sb.return_value = MySb()
            result = _handle_triage({"symptoms": "stomach pain, nausea"}, {})
            assert result["status"] == "SPECIALTY_FOUND"

    @patch("app.services.triage_engine.get_supabase")
    def test_no_matching_symptoms(self, mock_sb):
        from app.api.vapi_tools.triage import _handle_triage

        class EmptyQuery:
            def select(self, *_a, **_kw): return self
            def ilike(self, *_a, **_kw): return self
            def execute(self):
                resp = MagicMock()
                resp.data = []
                return resp

        class MySb:
            def table(self, _name): return EmptyQuery()

        mock_sb.return_value = MySb()
        result = _handle_triage({"symptoms": ["xyz unknown symptom"]}, {})
        assert result["status"] == "NEED_MORE_INFO"


class TestListSpecialties:
    @patch("app.services.triage_engine.get_supabase")
    def test_returns_specialties(self, mock_sb):
        from app.api.vapi_tools.triage import _handle_list_specialties
        mock_sb.return_value = FakeSupabase({
            "specialties": FakeQueryBuilder([
                {"id": "1", "name": "Cardiology", "description": "Heart"},
                {"id": "2", "name": "Dermatology", "description": "Skin"},
            ]),
        })
        result = _handle_list_specialties({}, {})
        assert result["status"] == "OK"
        assert len(result["specialties"]) == 2
        assert "Cardiology" in result["message"]
        assert "Dermatology" in result["message"]
