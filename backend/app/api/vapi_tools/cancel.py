from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.api.vapi_helpers import handle_tool_calls
from app.supabase import get_supabase

router = APIRouter()


def _handle_cancel(args: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    appointment_id = args.get("appointment_id")
    patient_id = args.get("patient_id")
    if not appointment_id:
        return {"status": "INVALID", "message": "I need to know which appointment to cancel."}

    sb = get_supabase()

    # Verify it exists and is active
    res = (
        sb.table("appointments")
        .select("id,patient_id,status,doctors(full_name)")
        .eq("id", appointment_id)
        .limit(1)
        .execute()
    )
    data = getattr(res, "data", None) or []
    if not data:
        return {"status": "NOT_FOUND", "message": "I couldn't find that appointment."}

    appt = data[0]

    # SECURITY: Verify the appointment belongs to the requesting patient
    if patient_id and appt.get("patient_id") and appt["patient_id"] != patient_id:
        return {"status": "NOT_FOUND", "message": "I couldn't find that appointment."}

    if appt["status"] != "CONFIRMED":
        return {"status": "INVALID", "message": "That appointment is already cancelled or completed."}

    # Cancel it
    sb.table("appointments").update({"status": "CANCELLED"}).eq("id", appointment_id).execute()

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
