from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.api.vapi_helpers import get_call_id, handle_tool_calls, set_call_context
from app.services.triage_engine import triage_symptoms, get_all_specialties

router = APIRouter()


def _handle_triage(args: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    symptoms = args.get("symptoms") or []
    if isinstance(symptoms, str):
        symptoms = [s.strip() for s in symptoms.split(",") if s.strip()]

    answers = args.get("answers") or {}

    result = triage_symptoms(symptoms, answers)

    if result.specialty_determined:
        call_id = get_call_id(payload)
        set_call_context(call_id, specialty_id=result.specialty_id)
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
    return {
        "status": "OK",
        "specialties": specialties,
        "message": f"We have specialists in: {', '.join(names)}. Which would you prefer?",
    }


@router.post("/triage")
async def triage(request: Request):
    payload = await request.json()
    return handle_tool_calls(payload, _handle_triage)


@router.post("/list-specialties")
async def list_specialties(request: Request):
    payload = await request.json()
    return handle_tool_calls(payload, _handle_list_specialties)
