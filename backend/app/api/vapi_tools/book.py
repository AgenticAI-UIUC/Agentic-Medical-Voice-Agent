from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request

from app.api.vapi_helpers import get_call_id, handle_tool_calls
from app.services.time_utils import format_for_voice
from app.supabase import get_supabase

router = APIRouter()


def _handle_book(args: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    patient_id = args.get("patient_id")
    doctor_id = args.get("doctor_id")
    start_at = args.get("start_at")
    end_at = args.get("end_at")

    if not all([patient_id, doctor_id, start_at, end_at]):
        return {"status": "INVALID", "message": "Missing required booking information."}

    # Validate and parse datetimes before touching the database
    if not isinstance(start_at, str) or not isinstance(end_at, str):
        return {"status": "INVALID", "message": "Start and end times must be valid date strings."}

    try:
        start_dt = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return {"status": "INVALID", "message": "I couldn't understand those appointment times. Could you try again?"}

    if start_dt >= end_dt:
        return {"status": "INVALID", "message": "The appointment end time must be after the start time."}

    cancel_appointment_id = args.get("cancel_appointment_id")

    sb = get_supabase()
    vapi_call_id = get_call_id(payload)

    # Get doctor name for confirmation message
    doc_res = sb.table("doctors").select("full_name").eq("id", doctor_id).limit(1).execute()
    doc_data = getattr(doc_res, "data", None) or []
    doctor_name = doc_data[0]["full_name"] if doc_data else "your doctor"

    row: dict[str, Any] = {
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "start_at": start_at,
        "end_at": end_at,
        "specialty_id": args.get("specialty_id"),
        "follow_up_from_id": args.get("follow_up_from_id"),
        "reason": (args.get("reason") or "").strip() or None,
        "symptoms": (args.get("symptoms") or "").strip() or None,
        "severity_description": (args.get("severity_description") or "").strip() or None,
        "severity_rating": args.get("severity_rating"),
        "urgency": args.get("urgency", "ROUTINE"),
        "status": "CONFIRMED",
        "vapi_call_id": vapi_call_id,
    }

    try:
        res = sb.table("appointments").insert(row).execute()
    except Exception as e:
        err_msg = str(e)
        if "unique_doctor_appointment" in err_msg:
            return {
                "status": "TAKEN",
                "message": "Sorry, that time was just booked. Would you like to pick another time?",
            }
        raise

    ins = getattr(res, "data", None) or []
    if not ins:
        return {"status": "ERROR", "message": "Something went wrong booking your appointment."}

    appointment = ins[0]
    when = format_for_voice(start_dt)

    # If rescheduling, cancel the original appointment now that the new one is confirmed
    if cancel_appointment_id:
        sb.table("appointments").update({"status": "CANCELLED"}).eq(
            "id", cancel_appointment_id
        ).eq("status", "CONFIRMED").execute()
        return {
            "status": "CONFIRMED",
            "appointment_id": appointment["id"],
            "doctor_name": doctor_name,
            "message": (
                f"All set — your previous appointment has been cancelled and "
                f"you're rebooked with {doctor_name} for {when}."
            ),
        }

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