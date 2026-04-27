"""Tests for the emergency red-flag classifier in triage_engine."""

from __future__ import annotations

import pytest

from app.services.triage_engine import classify_emergency


# --- Should trigger emergency ---


@pytest.mark.parametrize(
    "symptoms, expected_category",
    [
        # Cardiac
        (["chest pain"], "cardiac emergency"),
        (["I have crushing chest pressure"], "cardiac emergency"),
        (["heart attack"], "cardiac emergency"),
        (["tight chest pain radiating to arm"], "cardiac emergency"),
        # Stroke
        (["stroke symptoms"], "possible stroke"),
        (["face drooping slurred speech"], "possible stroke"),
        (["sudden weakness in left arm"], "possible stroke"),
        # Breathing
        (["can't breathe"], "respiratory emergency"),
        (["my child is not breathing"], "respiratory emergency"),
        (["choking on food"], "respiratory emergency"),
        (["severe shortness of breath"], "respiratory emergency"),
        # Bleeding / trauma
        (["severe bleeding won't stop"], "severe bleeding or trauma"),
        (["gunshot wound"], "severe bleeding or trauma"),
        (["uncontrollable bleeding"], "severe bleeding or trauma"),
        # Consciousness
        (["unconscious"], "loss of consciousness or prolonged seizure"),
        (
            ["unresponsive and not waking up"],
            "loss of consciousness or prolonged seizure",
        ),
        # Anaphylaxis
        (["anaphylaxis"], "possible anaphylaxis"),
        (["throat closing up"], "possible anaphylaxis"),
        # Mental health
        (["want to kill myself"], "mental health crisis"),
        (["suicidal thoughts"], "mental health crisis"),
        (["I overdosed on pills"], "mental health crisis"),
        # Poisoning
        (["my child swallowed bleach"], "possible poisoning"),
        (["poison ingested"], "possible poisoning"),
    ],
)
def test_emergency_detected(symptoms: list[str], expected_category: str) -> None:
    is_emergency, category, message = classify_emergency(symptoms)
    assert is_emergency is True
    assert category == expected_category
    assert message is not None
    assert len(message) > 0


def test_mental_health_crisis_gives_988_message() -> None:
    _, _, message = classify_emergency(["suicidal thoughts"])
    assert "988" in message
    assert "Crisis" in message


def test_general_emergency_gives_911_message() -> None:
    _, _, message = classify_emergency(["chest pain"])
    assert "911" in message
    assert "emergency room" in message


# --- Should NOT trigger emergency ---


@pytest.mark.parametrize(
    "symptoms",
    [
        ["headache"],
        ["runny nose and cough"],
        ["back pain for two weeks"],
        ["knee hurts when I walk"],
        ["mild fever"],
        ["rash on my arm"],
        ["stomach ache"],
        ["sore throat"],
        ["I feel tired all the time"],
        [],
    ],
)
def test_non_emergency(symptoms: list[str]) -> None:
    is_emergency, category, message = classify_emergency(symptoms)
    assert is_emergency is False
    assert category is None
    assert message is None
