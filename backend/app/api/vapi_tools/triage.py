from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Request

from app.api.vapi_helpers import handle_tool_calls
from app.services.triage_engine import triage_symptoms, get_all_specialties

router = APIRouter()


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return str(value).strip()
    return ""


def _split_symptom_text(text: str) -> list[str]:
    return [
        s.strip(" .")
        for s in re.split(r",|\band\b", text, flags=re.IGNORECASE)
        if s.strip(" .")
    ]


def _normalize_symptoms(raw: Any) -> list[str]:
    if raw is None:
        return []

    items = raw if isinstance(raw, (list, tuple, set)) else [raw]
    symptoms: list[str] = []
    for item in items:
        text = _coerce_text(item)
        if not text:
            continue
        symptoms.extend(_split_symptom_text(text))
    return symptoms


def _normalize_answers(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}

    answers: dict[str, str] = {}
    for question, response in raw.items():
        question_text = _coerce_text(question)
        response_text = _coerce_text(response)
        if question_text and response_text:
            answers[question_text] = response_text
    return answers


def _handle_triage(args: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    symptoms = _normalize_symptoms(args.get("symptoms"))
    answers = _normalize_answers(args.get("answers"))

    result = triage_symptoms(symptoms, answers)

    if result.is_emergency:
        return {
            "status": "EMERGENCY",
            "specialty_determined": False,
            "is_emergency": True,
            "emergency_category": result.emergency_category,
            "message": result.emergency_message,
        }

    if result.specialty_determined:
        return {
            "status": "SPECIALTY_FOUND",
            "specialty_determined": True,
            "specialty_id": result.specialty_id,
            "specialty_name": result.specialty_name,
            "confidence": result.confidence,
            "top_candidates": result.top_candidates,
            "message": (
                f"Based on your symptoms, I'd recommend seeing a {result.specialty_name} specialist. "
                "Does that sound right to you?"
            ),
        }

    return {
        "status": "NEED_MORE_INFO",
        "specialty_determined": False,
        "confidence": result.confidence,
        "follow_up_questions": result.follow_up_questions,
        "top_candidates": result.top_candidates,
        "message": "I need a bit more information to find the right specialist for you.",
    }


def _handle_list_specialties(args: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    specialties = get_all_specialties()
    names = [s["name"] for s in specialties]
    has_general_practice = any(name == "General Practice" for name in names)
    if has_general_practice:
        message = (
            "If you're not sure which specialist is best, we can start with General Practice. "
            "A GP can evaluate you first and guide you to a specialist if needed. "
            f"We also have specialists in: {', '.join(names)}. Which would you prefer?"
        )
    else:
        message = f"We have specialists in: {', '.join(names)}. Which would you prefer?"
    return {
        "status": "OK",
        "specialties": specialties,
        "message": message,
    }


@router.post("/triage")
async def triage(request: Request):
    payload = await request.json()
    return handle_tool_calls(payload, _handle_triage)


@router.post("/list-specialties")
async def list_specialties(request: Request):
    payload = await request.json()
    return handle_tool_calls(payload, _handle_list_specialties)
