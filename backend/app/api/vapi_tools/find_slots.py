from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.api.vapi_helpers import handle_tool_calls
from app.services.slot_engine import find_slots_with_extension

router = APIRouter()

def _handle_find_slots(args: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    specialty_id = args.get("specialty_id")
    doctor_id = args.get("doctor_id")
    preferred_day = args.get("preferred_day", "")
    preferred_time = args.get("preferred_time", "")

    if not specialty_id and not doctor_id:
        return {
            "status": "INVALID",
            "message": "I need to know the specialty to search for available times.",
            "slots": [],
        }

    result = find_slots_with_extension(
        specialty_id=specialty_id,
        doctor_id=doctor_id,
        preferred_day=preferred_day,
        preferred_time=preferred_time,
    )
    slots = result["slots"]
    window_note = result["window_note"]

    if not slots:
        return {
            "status": "NO_SLOTS",
            "message": "I couldn't find any available times. Would you like to try a different time or look further out?",
            "slots": [],
        }

    if doctor_id and not specialty_id:
        labels = [s["label"] for s in slots[:3]]
    else:
        labels = [f"{s['label']} with {s['doctor_name']}" for s in slots[:3]]
    spoken = labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " or " + labels[-1]

    if window_note:
        message = f"{window_note}: {spoken}. Which one works best?"
    else:
        message = f"I found these options: {spoken}. Which one works best?"

    return {
        "status": "OK",
        "slots": slots,
        "message": message,
    }


@router.post("/find-slots")
async def find_slots(request: Request):
    payload = await request.json()
    return handle_tool_calls(payload, _handle_find_slots)
