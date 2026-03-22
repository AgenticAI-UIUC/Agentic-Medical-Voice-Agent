from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.api.vapi_helpers import handle_tool_calls
from app.services.slot_engine import find_slots_for_specialty, find_available_slots

router = APIRouter()

def _handle_find_slots(args: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    specialty_id = args.get("specialty_id")
    doctor_id = args.get("doctor_id")
    preferred_day = args.get("preferred_day", "")
    preferred_time = args.get("preferred_time", "")

    if doctor_id:
        # Direct doctor lookup (e.g. follow-up with same doctor)
        slots = find_available_slots(doctor_id, preferred_day, preferred_time)
        if not slots:
            return {
                "status": "NO_SLOTS",
                "message": "I couldn't find any available times for that doctor in that window. Would you like to try a different time?",
                "slots": [],
            }

        labels = [s["label"] for s in slots[:3]]
        spoken = labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " or " + labels[-1]
        return {
            "status": "OK",
            "slots": slots,
            "message": f"I have {spoken}. Which one works best?",
        }

    if not specialty_id:
        return {
            "status": "INVALID",
            "message": "I need to know the specialty to search for available times.",
            "slots": [],
        }

    slots = find_slots_for_specialty(specialty_id, preferred_day, preferred_time)
    if not slots:
        return {
            "status": "NO_SLOTS",
            "message": "I couldn't find any available times in that window. Would you like to try a different time or look further out?",
            "slots": [],
        }

    labels = [f"{s['label']} with {s['doctor_name']}" for s in slots[:3]]
    spoken = labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " or " + labels[-1]
    return {
        "status": "OK",
        "slots": slots,
        "message": f"I found these options: {spoken}. Which one works best?",
    }


@router.post("/find-slots")
async def find_slots(request: Request):
    payload = await request.json()
    return handle_tool_calls(payload, _handle_find_slots)
