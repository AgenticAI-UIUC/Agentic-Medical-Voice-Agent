from __future__ import annotations

import pytest

from app.services import triage_engine
from tests.support import MockQuery, MockSupabase


def test_classify_answer_handles_affirmative_negative_and_neutral() -> None:
    assert triage_engine._classify_answer("yes definitely") == 1.0
    assert triage_engine._classify_answer("no never") == -1.0
    assert triage_engine._classify_answer("maybe sometimes") == 0.0


def test_classify_answer_handles_non_string_inputs() -> None:
    assert triage_engine._classify_answer(True) == 1.0
    assert triage_engine._classify_answer(False) == -1.0
    assert triage_engine._classify_answer(11) == 0.0
    assert triage_engine._classify_answer(None) == 0.0


def test_triage_symptoms_prompts_for_missing_symptoms() -> None:
    result = triage_engine.triage_symptoms([])

    assert result.specialty_determined is False
    assert result.follow_up_questions == ["Could you describe your symptoms?"]


def test_triage_symptoms_short_circuits_emergencies(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_get_supabase() -> None:
        raise AssertionError("triage_symptoms should not query Supabase for emergencies")

    monkeypatch.setattr(triage_engine, "get_supabase", fail_get_supabase)

    result = triage_engine.triage_symptoms(["crushing chest pain"])

    assert result.is_emergency is True
    assert result.emergency_category == "cardiac emergency"


def test_triage_symptoms_returns_fallback_when_no_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    sb = MockSupabase(tables={"symptom_specialty_map": [MockQuery(data=[])]})
    monkeypatch.setattr(triage_engine, "get_supabase", lambda: sb)

    result = triage_engine.triage_symptoms(["mystery symptom"])

    assert result.specialty_determined is False
    assert "wasn't able to match" in result.follow_up_questions[0]


def test_triage_symptoms_returns_confident_specialty(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        {
            "symptom": "rash",
            "specialty_id": "derm",
            "weight": 3,
            "follow_up_questions": ["Is the rash itchy?"],
            "specialties": {"id": "derm", "name": "Dermatology"},
        },
        {
            "symptom": "rash",
            "specialty_id": "allergy",
            "weight": 1,
            "follow_up_questions": ["Any swelling?"],
            "specialties": {"id": "allergy", "name": "Allergy"},
        },
    ]
    sb = MockSupabase(tables={"symptom_specialty_map": [MockQuery(data=rows)]})
    monkeypatch.setattr(triage_engine, "get_supabase", lambda: sb)

    result = triage_engine.triage_symptoms(["rash"])

    assert result.specialty_determined is True
    assert result.specialty_id == "derm"
    assert result.specialty_name == "Dermatology"
    assert result.confidence == 0.75
    assert result.top_candidates[0]["specialty_id"] == "derm"


def test_triage_symptoms_maps_migraines_and_nausea_to_neurology(monkeypatch: pytest.MonkeyPatch) -> None:
    migraine_rows = [
        {
            "symptom": "migraine",
            "specialty_id": "neuro",
            "weight": 2,
            "follow_up_questions": ["Do you see visual disturbances before the migraine?"],
            "specialties": {"id": "neuro", "name": "Neurology"},
        }
    ]
    headache_rows = [
        {
            "symptom": "headache",
            "specialty_id": "neuro",
            "weight": 1.5,
            "follow_up_questions": ["Where is the pain located?"],
            "specialties": {"id": "neuro", "name": "Neurology"},
        }
    ]
    nausea_rows = [
        {
            "symptom": "nausea",
            "specialty_id": "gastro",
            "weight": 1.5,
            "follow_up_questions": ["Have you been vomiting?"],
            "specialties": {"id": "gastro", "name": "Gastroenterology"},
        }
    ]
    sb = MockSupabase(
        tables={
            "symptom_specialty_map": [
                MockQuery(data=[]),
                MockQuery(data=migraine_rows),
                MockQuery(data=headache_rows),
                MockQuery(data=nausea_rows),
            ]
        }
    )
    monkeypatch.setattr(triage_engine, "get_supabase", lambda: sb)

    result = triage_engine.triage_symptoms(["migraines", "nausea"])

    assert result.specialty_determined is True
    assert result.specialty_id == "neuro"
    assert result.specialty_name == "Neurology"
    assert result.confidence == 0.7


def test_triage_symptoms_uses_answers_to_break_ties(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        {
            "symptom": "rash",
            "specialty_id": "derm",
            "weight": 1,
            "follow_up_questions": ["Is the rash itchy?"],
            "specialties": {"id": "derm", "name": "Dermatology"},
        },
        {
            "symptom": "rash",
            "specialty_id": "allergy",
            "weight": 1,
            "follow_up_questions": ["Any sneezing?"],
            "specialties": {"id": "allergy", "name": "Allergy"},
        },
    ]
    sb = MockSupabase(tables={"symptom_specialty_map": [MockQuery(data=rows)]})
    monkeypatch.setattr(triage_engine, "get_supabase", lambda: sb)

    result = triage_engine.triage_symptoms(
        ["rash"],
        answers={"Is the rash itchy?": "yes absolutely"},
        confidence_threshold=0.7,
    )

    assert result.specialty_determined is True
    assert result.specialty_id == "derm"
    assert result.confidence == 0.71


def test_triage_symptoms_skips_already_answered_follow_ups(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        {
            "symptom": "rash",
            "specialty_id": "derm",
            "weight": 1,
            "follow_up_questions": ["Is the rash itchy?", "Any blistering?"],
            "specialties": {"id": "derm", "name": "Dermatology"},
        },
        {
            "symptom": "rash",
            "specialty_id": "allergy",
            "weight": 1,
            "follow_up_questions": ["Any sneezing?"],
            "specialties": {"id": "allergy", "name": "Allergy"},
        },
    ]
    sb = MockSupabase(tables={"symptom_specialty_map": [MockQuery(data=rows)]})
    monkeypatch.setattr(triage_engine, "get_supabase", lambda: sb)

    result = triage_engine.triage_symptoms(
        ["rash"],
        answers={"Is the rash itchy?": "maybe"},
        confidence_threshold=0.8,
    )

    assert result.specialty_determined is False
    assert "Is the rash itchy?" not in result.follow_up_questions
    assert result.follow_up_questions == ["Any blistering?", "Any sneezing?"]


def test_triage_symptoms_tolerates_non_string_symptoms_and_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        {
            "symptom": "rash",
            "specialty_id": "derm",
            "weight": 1,
            "follow_up_questions": ["Is the rash itchy?"],
            "specialties": {"id": "derm", "name": "Dermatology"},
        },
        {
            "symptom": "rash",
            "specialty_id": "allergy",
            "weight": 1,
            "follow_up_questions": ["Any sneezing?"],
            "specialties": {"id": "allergy", "name": "Allergy"},
        },
    ]
    sb = MockSupabase(
        tables={
            "symptom_specialty_map": [
                MockQuery(data=rows),
                MockQuery(data=[]),
            ]
        }
    )
    monkeypatch.setattr(triage_engine, "get_supabase", lambda: sb)

    result = triage_engine.triage_symptoms(
        ["rash", None, 4],
        answers={"Is the rash itchy?": True, "ignored": None},
        confidence_threshold=0.7,
    )

    assert result.specialty_determined is True
    assert result.specialty_id == "derm"
    assert result.confidence == 0.71


def test_get_all_specialties_returns_database_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    specialties = [
        {"id": "allergy", "name": "Allergy", "description": "Allergy care"},
        {"id": "derm", "name": "Dermatology", "description": "Skin care"},
    ]
    sb = MockSupabase(tables={"specialties": [MockQuery(data=specialties)]})
    monkeypatch.setattr(triage_engine, "get_supabase", lambda: sb)

    assert triage_engine.get_all_specialties() == specialties
