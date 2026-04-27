from __future__ import annotations

from app.api.vapi_tools import triage
from app.services.triage_engine import TriageResult


def test_handle_list_specialties_recommends_general_practice_when_available(
    monkeypatch,
) -> None:
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


def test_handle_list_specialties_falls_back_to_generic_message_without_gp(
    monkeypatch,
) -> None:
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
    assert (
        result["message"]
        == "We have specialists in: Neurology, Dermatology. Which would you prefer?"
    )


def test_handle_triage_normalizes_non_string_inputs(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_triage_symptoms(symptoms, answers, **kwargs):
        captured["symptoms"] = symptoms
        captured["answers"] = answers
        captured["description"] = kwargs.get("description")
        return TriageResult(
            specialty_determined=False,
            confidence=0.25,
            follow_up_questions=["When did this start?"],
        )

    monkeypatch.setattr(triage, "triage_symptoms", fake_triage_symptoms)

    result = triage._handle_triage(
        {
            "symptoms": ["headache", 4, None, "nausea and dizziness"],
            "answers": {
                "Is the pain constant?": True,
                2: "no",
                "ignored": None,
            },
        },
        {},
    )

    assert captured["symptoms"] == ["headache", "4", "nausea", "dizziness"]
    assert captured["answers"] == {
        "Is the pain constant?": "yes",
        "2": "no",
    }
    assert captured["description"] == ""
    assert result["status"] == "NEED_MORE_INFO"
    assert result["follow_up_questions"] == ["When did this start?"]


def test_handle_triage_ignores_non_mapping_answers(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_triage_symptoms(symptoms, answers, **kwargs):
        captured["symptoms"] = symptoms
        captured["answers"] = answers
        captured["description"] = kwargs.get("description")
        return TriageResult(
            specialty_determined=False,
            confidence=0.0,
            follow_up_questions=["Could you describe your symptoms?"],
        )

    monkeypatch.setattr(triage, "triage_symptoms", fake_triage_symptoms)

    triage._handle_triage({"symptoms": "headache", "answers": "yes"}, {})

    assert captured["symptoms"] == ["headache"]
    assert captured["answers"] == {}
    assert captured["description"] == "headache"


def test_handle_triage_passes_natural_language_description(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_triage_symptoms(symptoms, answers, **kwargs):
        captured["symptoms"] = symptoms
        captured["answers"] = answers
        captured["description"] = kwargs.get("description")
        return TriageResult(
            specialty_determined=True,
            specialty_id="cardiology",
            specialty_name="Cardiology",
            confidence=0.92,
        )

    monkeypatch.setattr(triage, "triage_symptoms", fake_triage_symptoms)

    result = triage._handle_triage(
        {
            "symptoms": ["chest discomfort"],
            "description": "It feels like an elephant is sitting on my chest.",
        },
        {},
    )

    assert captured["symptoms"] == ["chest discomfort"]
    assert captured["answers"] == {}
    assert captured["description"] == "It feels like an elephant is sitting on my chest."
    assert result["status"] == "SPECIALTY_FOUND"
