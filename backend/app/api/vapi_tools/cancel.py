from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.api.vapi_helpers import get_call_id, handle_tool_calls
from app.supabase import get_supabase

router = APIRouter()


def _is_valid_uuid(val: str) -> bool:
    import uuid

    try:
        uuid.UUID(val)
        return True
    except (ValueError, AttributeError):
        return False


def _handle_cancel(args: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    appointment_id = args.get("appointment_id")
    if not appointment_id:
        return {
            "status": "INVALID",
            "message": "I need to know which appointment to cancel.",
        }

    if not _is_valid_uuid(appointment_id):
        return {
            "status": "INVALID",
            "message": "The appointment ID is not valid. Please try finding the appointment again.",
        }

    sb = get_supabase()

    # Verify it exists and is active
    res = (
        sb.table("appointments")
        .select("id,status,doctors(full_name)")
        .eq("id", appointment_id)
        .limit(1)
        .execute()
    )
    data = getattr(res, "data", None) or []
    if not data:
        return {"status": "NOT_FOUND", "message": "I couldn't find that appointment."}

    appt = data[0]
    if appt["status"] != "CONFIRMED":
        return {
            "status": "INVALID",
            "message": "That appointment is already cancelled or completed.",
        }

    # Cancel it
    update_row = {"status": "CANCELLED"}
    vapi_call_id = get_call_id(payload)
    if vapi_call_id:
        update_row["vapi_call_id"] = vapi_call_id
    sb.table("appointments").update(update_row).eq("id", appointment_id).execute()

    doctor_name = appt.get("doctors", {}).get("full_name", "your doctor")
    return {
        "status": "CANCELLED",
        "appointment_id": appointment_id,
        "message": f"Your appointment with {doctor_name} has been cancelled.",
    }


@router.post("/cancel")
async def cancel(request: Request):
    payload = await request.json()
    return handle_tool_calls(payload, _handle_cancel)
