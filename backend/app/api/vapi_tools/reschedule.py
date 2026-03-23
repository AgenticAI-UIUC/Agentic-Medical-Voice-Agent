from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.api.vapi_helpers import handle_tool_calls
from app.services.slot_engine import find_slots_with_extension
from app.supabase import get_supabase

router = APIRouter()


def _handle_find_appointment(args: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Find a patient's existing appointment for rescheduling or cancellation."""
    patient_id = args.get("patient_id")
    if not patient_id:
        return {"status": "INVALID", "message": "I need your patient information first."}

    doctor_name = (args.get("doctor_name") or "").strip().lower()
    reason = (args.get("reason") or "").strip().lower()

    sb = get_supabase()

    query = (
        sb.table("appointments")
        .select("id,doctor_id,specialty_id,start_at,end_at,reason,symptoms,status,doctors(full_name)")
        .eq("patient_id", patient_id)
        .eq("status", "CONFIRMED")
        .order("start_at", desc=True)
        .limit(10)
    )

    res = query.execute()
    appointments = getattr(res, "data", None) or []

    if not appointments:
        return {
            "status": "NO_APPOINTMENTS",
            "message": "I don't see any upcoming appointments on file for you.",
        }

    # Try to narrow down by doctor name and/or reason
    matches = appointments
    if doctor_name:
        matches = [
            a for a in matches
            if doctor_name in (a.get("doctors", {}).get("full_name", "") or "").lower()
        ]
    if reason:
        matches = [
            a for a in matches
            if reason in (a.get("reason") or "").lower() or reason in (a.get("symptoms") or "").lower()
        ]

    if not matches:
        # Fall back to showing all
        matches = appointments

    if len(matches) == 1:
        appt = matches[0]
        doc_name = appt.get("doctors", {}).get("full_name", "your doctor")
        return {
            "status": "FOUND",
            "appointment": {
                "id": appt["id"],
                "doctor_id": appt["doctor_id"],
                "doctor_name": doc_name,
                "specialty_id": appt.get("specialty_id"),
                "start_at": appt["start_at"],
                "end_at": appt["end_at"],
                "reason": appt.get("reason"),
            },
            "message": f"I found your appointment with {doc_name}. Is this the one you mean?",
        }

    # Multiple matches — list them for the patient to pick
    options = []
    for a in matches[:5]:
        doc_name = a.get("doctors", {}).get("full_name", "Unknown")
        options.append({
            "id": a["id"],
            "doctor_name": doc_name,
            "start_at": a["start_at"],
            "reason": a.get("reason"),
        })

    return {
        "status": "MULTIPLE",
        "appointments": options,
        "message": f"I found {len(options)} appointments. Which one are you referring to?",
    }


def _handle_reschedule(args: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Cancel old appointment and find new slots for same specialty."""
    appointment_id = args.get("appointment_id")
    preferred_day = args.get("preferred_day", "")
    preferred_time = args.get("preferred_time", "")

    if not appointment_id:
        return {"status": "INVALID", "message": "I need to know which appointment to reschedule."}

    sb = get_supabase()

    # Fetch the original appointment
    res = (
        sb.table("appointments")
        .select("id,specialty_id,doctor_id,status")
        .eq("id", appointment_id)
        .limit(1)
        .execute()
    )
    data = getattr(res, "data", None) or []
    if not data:
        return {"status": "NOT_FOUND", "message": "I couldn't find that appointment."}

    appt = data[0]
    if appt["status"] != "CONFIRMED":
        return {"status": "INVALID", "message": "That appointment isn't active and can't be rescheduled."}

    specialty_id = appt.get("specialty_id")
    doctor_id = appt["doctor_id"]

    # Find new slots — prefer same specialty, fall back to same doctor
    result = find_slots_with_extension(
        specialty_id=specialty_id or None,
        doctor_id=None if specialty_id else doctor_id,
        preferred_day=preferred_day,
        preferred_time=preferred_time,
    )
    slots = result["slots"]
    window_note = result["window_note"]

    if not slots:
        return {
            "status": "NO_SLOTS",
            "original_appointment_id": appointment_id,
            "message": "I couldn't find any available times for rescheduling. Would you like to try a different window?",
            "slots": [],
        }

    if specialty_id:
        labels = [f"{s['label']} with {s['doctor_name']}" for s in slots[:3]]
    else:
        labels = [s["label"] for s in slots[:3]]
    spoken = labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " or " + labels[-1]

    if window_note:
        message = f"{window_note}: {spoken}. Which one works?"
    else:
        message = f"I can reschedule you to {spoken}. Which one works?"

    return {
        "status": "SLOTS_AVAILABLE",
        "original_appointment_id": appointment_id,
        "slots": slots,
        "message": message,
    }


@router.post("/find-appointment")
async def find_appointment(request: Request):
    payload = await request.json()
    return handle_tool_calls(payload, _handle_find_appointment)


@router.post("/reschedule")
async def reschedule(request: Request):
    payload = await request.json()
    return handle_tool_calls(payload, _handle_reschedule)
