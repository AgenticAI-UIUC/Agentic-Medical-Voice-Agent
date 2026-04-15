from __future__ import annotations

from app.api.vapi_tools import triage


def test_handle_list_specialties_recommends_general_practice_when_available(monkeypatch) -> None:
    monkeypatch.setattr(
        triage,
        "get_all_specialties",
        lambda: [
            {"id": "gp", "name": "General Practice", "description": "Primary care"},
            {"id": "neuro", "name": "Neurology", "description": "Nervous system"},
        ],
    )

    result = triage._handle_list_specialties({}, {})

    assert result["status"] == "OK"
    assert "start with General Practice" in result["message"]
    assert "guide you to a specialist if needed" in result["message"]


def test_handle_list_specialties_falls_back_to_generic_message_without_gp(monkeypatch) -> None:
    monkeypatch.setattr(
        triage,
        "get_all_specialties",
        lambda: [
            {"id": "neuro", "name": "Neurology", "description": "Nervous system"},
            {"id": "derm", "name": "Dermatology", "description": "Skin care"},
        ],
    )

    result = triage._handle_list_specialties({}, {})

    assert result["status"] == "OK"
    assert result["message"] == "We have specialists in: Neurology, Dermatology. Which would you prefer?"
