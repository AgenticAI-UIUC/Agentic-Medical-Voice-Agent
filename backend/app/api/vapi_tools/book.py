from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request

from app.api.vapi_helpers import (
    coerce_allowed_string,
    coerce_string,
    get_call_id,
    handle_tool_calls,
)
from app.services.slot_engine import validate_slot
from app.services.time_utils import format_for_voice
from app.supabase import get_supabase

router = APIRouter()

_ALLOWED_URGENCY = {"ROUTINE", "URGENT", "ER"}


def _handle_book(args: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    patient_id = coerce_string(args.get("patient_id"))
    doctor_id = coerce_string(args.get("doctor_id"))
    start_at = coerce_string(args.get("start_at"))
    end_at = coerce_string(args.get("end_at"))

    if not all([patient_id, doctor_id, start_at, end_at]):
        return {"status": "INVALID", "message": "Missing required booking information."}

    try:
        start_dt = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return {
            "status": "INVALID",
            "message": "I couldn't understand those appointment times. Could you try again?",
        }

    if start_dt >= end_dt:
        return {
            "status": "INVALID",
            "message": "The appointment end time must be after the start time.",
        }

    # Validate that the slot is real doctor availability
    slot_error = validate_slot(doctor_id, start_dt, end_dt)
    if slot_error:
        return {"status": "INVALID", "message": slot_error}

    sb = get_supabase()
    vapi_call_id = get_call_id(payload)

    # Get doctor name for confirmation message
    doc_res = (
        sb.table("doctors").select("full_name").eq("id", doctor_id).limit(1).execute()
    )
    doc_data = getattr(doc_res, "data", None) or []
    doctor_name = doc_data[0]["full_name"] if doc_data else "your doctor"

    urgency = (
        coerce_allowed_string(args.get("urgency"), _ALLOWED_URGENCY, default="ROUTINE")
        or "ROUTINE"
    )

    row: dict[str, Any] = {
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "start_at": start_at,
        "end_at": end_at,
        "specialty_id": coerce_string(args.get("specialty_id")) or None,
        "follow_up_from_id": coerce_string(args.get("follow_up_from_id")) or None,
        "reason": coerce_string(args.get("reason")) or None,
        "symptoms": coerce_string(args.get("symptoms")) or None,
        "severity_description": None,
        "severity_rating": None,
        "urgency": urgency,
        "status": "CONFIRMED",
        "vapi_call_id": vapi_call_id,
    }

    try:
        res = sb.table("appointments").insert(row).execute()
    except Exception as e:
        err_msg = str(e)
        if "unique_doctor_appointment" in err_msg or "no_doctor_overlap" in err_msg:
            return {
                "status": "TAKEN",
                "message": "Sorry, that time was just booked. Would you like to pick another time?",
            }
        raise

    ins = getattr(res, "data", None) or []
    if not ins:
        return {
            "status": "ERROR",
            "message": "Something went wrong booking your appointment.",
        }

    appointment = ins[0]
    when = format_for_voice(start_dt)

    return {
        "status": "CONFIRMED",
        "appointment_id": appointment["id"],
        "doctor_name": doctor_name,
        "message": f"All set — you're booked with {doctor_name} for {when}.",
    }


@router.post("/book")
async def book(request: Request):
    payload = await request.json()
    return handle_tool_calls(payload, _handle_book)
