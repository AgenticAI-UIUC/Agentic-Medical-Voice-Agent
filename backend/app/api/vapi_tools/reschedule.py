from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from datetime import datetime

from app.api.vapi_helpers import (
    coerce_bool,
    coerce_string,
    get_call_id,
    handle_tool_calls,
    is_valid_uuid,
)
from app.services.slot_engine import find_slots_for_specialty, validate_slot, is_next_available_request
from app.services.time_utils import format_for_voice, now_utc, parse_time_bucket
from app.supabase import get_supabase


def _format_start(start_at: str) -> str:
    """Convert a UTC start_at string to a voice-friendly local time label."""
    dt = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
    return format_for_voice(dt)


def _parse_start(start_at: str) -> datetime:
    return datetime.fromisoformat(start_at.replace("Z", "+00:00"))

router = APIRouter()


def _should_retry_with_any(preferred_day: str, preferred_time: str) -> bool:
    return is_next_available_request(preferred_day) and parse_time_bucket(preferred_time) != "any"


def _relaxed_reschedule_message(preferred_time: str, slots: list[dict[str, Any]]) -> str:
    labels = [s["label"] for s in slots[:3]]
    spoken = labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " or " + labels[-1]
    bucket = parse_time_bucket(preferred_time)
    bucket_text = "morning" if bucket == "morning" else "afternoon"
    return (
        f"I don't see any {bucket_text} openings as soon as possible, "
        f"but I can reschedule you to {spoken}. Which one works?"
    )


def _handle_find_appointment(args: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Find a patient's existing appointment for rescheduling or cancellation."""
    patient_id = coerce_string(args.get("patient_id"))
    if not patient_id:
        return {"status": "INVALID", "message": "I need your patient information first."}

    doctor_name = coerce_string(args.get("doctor_name")).lower()
    reason = coerce_string(args.get("reason")).lower()
    include_past = coerce_bool(args.get("include_past"))

    sb = get_supabase()

    query = (
        sb.table("appointments")
        .select("id,doctor_id,specialty_id,start_at,end_at,reason,symptoms,status,doctors(full_name)")
        .eq("patient_id", patient_id)
        .order("start_at", desc=True)
        .limit(20)
    )

    res = query.execute()
    appointments = getattr(res, "data", None) or []
    now = now_utc()

    if include_past:
        appointments = [
            a for a in appointments
            if a.get("status") in {"CONFIRMED", "COMPLETED"}
        ]
    else:
        appointments = [
            a for a in appointments
            if a.get("status") == "CONFIRMED"
            and _parse_start(a["start_at"]) >= now
        ]

    if not appointments:
        return {
            "status": "NO_APPOINTMENTS",
            "message": (
                "I couldn't find a previous appointment on file for that follow-up."
                if include_past
                else "I don't see any upcoming appointments on file for you."
            ),
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
        label = _format_start(appt["start_at"])
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
                "label": label,
            },
            "message": f"I found your appointment with {doc_name} on {label}. Is this the one you mean?",
        }

    # Multiple matches — list them for the patient to pick
    options = []
    for a in matches[:5]:
        doc_name = a.get("doctors", {}).get("full_name", "Unknown")
        label = _format_start(a["start_at"])
        options.append({
            "id": a["id"],
            "doctor_name": doc_name,
            "start_at": a["start_at"],
            "label": label,
            "reason": a.get("reason"),
        })

    return {
        "status": "MULTIPLE",
        "appointments": options,
        "message": f"I found {len(options)} appointments. Which one are you referring to?",
    }


def _handle_reschedule(args: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Cancel old appointment and find new slots for same specialty."""
    appointment_id = coerce_string(args.get("appointment_id"))
    patient_id = coerce_string(args.get("patient_id")) or None
    preferred_day = coerce_string(args.get("preferred_day"))
    preferred_time = coerce_string(args.get("preferred_time"))

    if not appointment_id:
        return {"status": "INVALID", "message": "I need to know which appointment to reschedule."}

    if not is_valid_uuid(appointment_id):
        return {"status": "INVALID", "message": "The appointment ID is not valid. Please try finding the appointment again."}

    sb = get_supabase()

    # Fetch the original appointment — verify patient ownership
    query = (
        sb.table("appointments")
        .select("id,patient_id,specialty_id,doctor_id,status")
        .eq("id", appointment_id)
    )
    if patient_id:
        query = query.eq("patient_id", patient_id)

    res = query.limit(1).execute()
    data = getattr(res, "data", None) or []
    if not data:
        return {"status": "NOT_FOUND", "message": "I couldn't find that appointment."}

    appt = data[0]
    resolved_patient_id = patient_id or appt.get("patient_id")
    if appt["status"] != "CONFIRMED":
        return {"status": "INVALID", "message": "That appointment isn't active and can't be rescheduled."}

    specialty_id = appt.get("specialty_id")
    doctor_id = appt["doctor_id"]

    # Find new slots — prefer same specialty, fall back to same doctor
    if specialty_id:
        slots = find_slots_for_specialty(specialty_id, preferred_day, preferred_time)
    else:
        from app.services.slot_engine import find_available_slots
        slots = find_available_slots(doctor_id, preferred_day, preferred_time)
        for s in slots:
            s["doctor_id"] = doctor_id

    if not slots and _should_retry_with_any(preferred_day, preferred_time):
        if specialty_id:
            slots = find_slots_for_specialty(specialty_id, preferred_day, "any")
        else:
            from app.services.slot_engine import find_available_slots
            slots = find_available_slots(doctor_id, preferred_day, "any")
            for s in slots:
                s["doctor_id"] = doctor_id
        if slots:
            return {
                "status": "SLOTS_AVAILABLE",
                "original_appointment_id": appointment_id,
                "patient_id": resolved_patient_id,
                "slots": slots,
                "message": _relaxed_reschedule_message(preferred_time, slots),
            }

    if not slots:
        return {
            "status": "NO_SLOTS",
            "original_appointment_id": appointment_id,
            "patient_id": resolved_patient_id,
            "message": "I couldn't find any available times for rescheduling. Would you like to try a different window?",
            "slots": [],
        }

    labels = [s["label"] for s in slots[:3]]
    spoken = labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " or " + labels[-1]
    return {
        "status": "SLOTS_AVAILABLE",
        "original_appointment_id": appointment_id,
        "patient_id": resolved_patient_id,
        "slots": slots,
        "message": f"I can reschedule you to {spoken}. Which one works?",
    }


def _handle_reschedule_finalize(args: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Atomically book a new slot and cancel the original appointment via a single DB transaction."""
    original_appointment_id = coerce_string(args.get("original_appointment_id"))
    patient_id = coerce_string(args.get("patient_id"))
    doctor_id = coerce_string(args.get("doctor_id"))
    start_at = coerce_string(args.get("start_at"))
    end_at = coerce_string(args.get("end_at"))

    if not all([original_appointment_id, patient_id, doctor_id, start_at, end_at]):
        return {"status": "INVALID", "message": "Missing required rescheduling information."}

    for id_field, id_val in [("original_appointment_id", original_appointment_id),
                              ("patient_id", patient_id), ("doctor_id", doctor_id)]:
        if not is_valid_uuid(id_val):
            return {"status": "INVALID", "message": f"The {id_field} is not valid. Please try again."}

    # Parse start/end times
    try:
        start_dt = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return {"status": "INVALID", "message": "I couldn't understand the appointment time."}

    if start_dt >= end_dt:
        return {"status": "INVALID", "message": "The appointment end time must be after the start time."}

    # Validate that the new slot is real doctor availability
    slot_error = validate_slot(doctor_id, start_dt, end_dt)
    if slot_error:
        return {"status": "INVALID", "message": slot_error}

    sb = get_supabase()

    # Fetch original appointment metadata (for fields to carry over)
    res = (
        sb.table("appointments")
        .select("id,specialty_id,reason,symptoms,severity_description,severity_rating,urgency")
        .eq("id", original_appointment_id)
        .limit(1)
        .execute()
    )
    data = getattr(res, "data", None) or []
    if not data:
        return {"status": "NOT_FOUND", "message": "I couldn't find the original appointment."}

    original = data[0]

    # Get doctor name
    doc_res = sb.table("doctors").select("full_name").eq("id", doctor_id).limit(1).execute()
    doc_data = getattr(doc_res, "data", None) or []
    doctor_name = doc_data[0]["full_name"] if doc_data else "your doctor"

    vapi_call_id = get_call_id(payload)

    # Atomically insert new appointment + cancel old one in a single DB transaction
    rpc_params = {
        "p_original_appointment_id": original_appointment_id,
        "p_patient_id": patient_id,
        "p_doctor_id": doctor_id,
        "p_start_at": start_at,
        "p_end_at": end_at,
        "p_specialty_id": coerce_string(args.get("specialty_id")) or original.get("specialty_id"),
        "p_reason": coerce_string(args.get("reason")) or original.get("reason"),
        "p_symptoms": original.get("symptoms"),
        "p_severity_description": original.get("severity_description"),
        "p_severity_rating": original.get("severity_rating"),
        "p_urgency": original.get("urgency", "ROUTINE"),
        "p_vapi_call_id": vapi_call_id,
    }

    try:
        rpc_res = sb.rpc("reschedule_appointment", rpc_params).execute()
    except Exception as e:
        if "unique_doctor_appointment" in str(e) or "no_doctor_overlap" in str(e):
            return {
                "status": "TAKEN",
                "message": "Sorry, that time was just booked. Would you like to pick another time?",
            }
        raise

    rpc_data = getattr(rpc_res, "data", None)
    if not rpc_data:
        return {"status": "ERROR", "message": "Something went wrong with the reschedule."}

    result = rpc_data if isinstance(rpc_data, dict) else rpc_data[0] if isinstance(rpc_data, list) else {}
    status = result.get("status")

    if status == "NOT_FOUND":
        return {"status": "NOT_FOUND", "message": "I couldn't find the original appointment."}

    if status == "NOT_ACTIVE":
        return {"status": "INVALID", "message": "The original appointment is no longer active."}

    if status != "RESCHEDULED":
        return {"status": "ERROR", "message": "Something went wrong with the reschedule."}

    when = format_for_voice(start_dt)
    return {
        "status": "RESCHEDULED",
        "appointment_id": result.get("new_appointment_id"),
        "original_appointment_id": original_appointment_id,
        "doctor_name": doctor_name,
        "message": (
            f"Your appointment has been rescheduled. You're now booked with "
            f"{doctor_name} on {when}. Your previous appointment has been cancelled."
        ),
    }


@router.post("/find-appointment")
async def find_appointment(request: Request):
    payload = await request.json()
    return handle_tool_calls(payload, _handle_find_appointment)


@router.post("/reschedule")
async def reschedule(request: Request):
    payload = await request.json()
    return handle_tool_calls(payload, _handle_reschedule)


@router.post("/reschedule-finalize")
async def reschedule_finalize(request: Request):
    payload = await request.json()
    return handle_tool_calls(payload, _handle_reschedule_finalize)
