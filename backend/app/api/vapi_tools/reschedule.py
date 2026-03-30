from __future__ import annotations

import logging
import time as _time
from datetime import datetime
from threading import Lock
from typing import Any

from fastapi import APIRouter, Request

from app.api.vapi_helpers import get_call_id, handle_tool_calls
from app.services.slot_engine import (
    find_available_slots,
    find_slots_for_specialty,
    validate_slot,
    _check_overlap,
)
from app.services.time_utils import format_for_voice, now_utc
from app.supabase import get_supabase

logger = logging.getLogger(__name__)

router = APIRouter()
MAX_VOICE_OPTIONS = 3
MAX_APPOINTMENT_OPTIONS = 3

# ---------------------------------------------------------------------------
# Lightweight in-memory slot cache keyed by VAPI call_id.
#
# When _handle_reschedule offers slots to the caller, it caches them here so
# that the finalization step can look up the *exact* slot the patient chose
# by slot_number — eliminating the risk of VAPI's LLM passing the wrong
# doctor_id / start_at / end_at.
# ---------------------------------------------------------------------------
_slot_cache: dict[str, dict[str, Any]] = {}
_cache_lock = Lock()
_CACHE_TTL_SECONDS = 600  # 10 minutes — generous for a voice call


def _cache_slots(call_id: str, appointment_id: str, slots: list[dict[str, Any]]) -> None:
    with _cache_lock:
        _slot_cache[call_id] = {
            "appointment_id": appointment_id,
            "slots": slots,
            "expires": _time.monotonic() + _CACHE_TTL_SECONDS,
        }
        # Purge expired entries to prevent unbounded growth
        now = _time.monotonic()
        expired = [k for k, v in _slot_cache.items() if v["expires"] < now]
        for k in expired:
            del _slot_cache[k]


def _pop_cached_slot(call_id: str, slot_number: int) -> dict[str, Any] | None:
    """Look up a previously offered slot by call_id + slot_number.

    Returns a dict with slot fields + original_appointment_id, or None on miss.
    """
    with _cache_lock:
        entry = _slot_cache.get(call_id)
        if not entry or entry["expires"] < _time.monotonic():
            return None
        for slot in entry["slots"]:
            if slot.get("slot_number") == slot_number:
                return {**slot, "original_appointment_id": entry["appointment_id"]}
    return None


def _prepare_slot_choices(slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    trimmed = slots[:MAX_VOICE_OPTIONS]
    return [{**slot, "slot_number": index} for index, slot in enumerate(trimmed, start=1)]


def _spoken_slot_list(slots: list[dict[str, Any]]) -> str:
    phrases = []
    for slot in slots:
        phrase = f"option {slot['slot_number']} is {slot['label']}"
        if slot.get("doctor_name"):
            phrase += f" with {slot['doctor_name']}"
        phrases.append(phrase)

    if len(phrases) == 1:
        return phrases[0]
    if len(phrases) == 2:
        return " or ".join(phrases)
    return ", ".join(phrases[:-1]) + ", or " + phrases[-1]


def _appointment_voice_label(appointment: dict[str, Any]) -> str:
    start_at = appointment["start_at"]
    start_dt = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
    when = format_for_voice(start_dt)
    doctor_name = appointment.get("doctors", {}).get("full_name", "your doctor")
    reason = (appointment.get("reason") or "").strip()

    phrase = f"with {doctor_name} on {when}"
    if reason:
        phrase += f" for {reason}"
    return phrase


def _handle_find_appointment(args: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Find a patient's existing appointment for rescheduling or cancellation.

    SAFETY: Only returns future confirmed appointments so the caller cannot
    be told a past appointment is "upcoming".
    """
    patient_id = args.get("patient_id")
    if not patient_id:
        return {"status": "INVALID", "message": "I need your patient information first."}

    doctor_name = (args.get("doctor_name") or "").strip().lower()
    reason = (args.get("reason") or "").strip().lower()

    sb = get_supabase()
    now = now_utc()

    # SAFETY-CRITICAL: Filter to non-ended appointments only.
    # Use end_at > now so that in-progress appointments (started but not yet
    # ended) are still visible for rescheduling or cancellation.
    query = (
        sb.table("appointments")
        .select("id,doctor_id,specialty_id,start_at,end_at,reason,symptoms,status,doctors(full_name)")
        .eq("patient_id", patient_id)
        .eq("status", "CONFIRMED")
        .gt("end_at", now.isoformat())
        .order("start_at", desc=False)
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
    for index, a in enumerate(matches[:MAX_APPOINTMENT_OPTIONS], start=1):
        doc_name = a.get("doctors", {}).get("full_name", "Unknown")
        options.append({
            "appointment_number": index,
            "id": a["id"],
            "doctor_name": doc_name,
            "start_at": a["start_at"],
            "reason": a.get("reason"),
            "label": _appointment_voice_label(a),
        })

    option_phrases = [
        f"option {appointment['appointment_number']} is {appointment['label']}"
        for appointment in options
    ]
    if len(option_phrases) == 1:
        spoken = option_phrases[0]
    elif len(option_phrases) == 2:
        spoken = " or ".join(option_phrases)
    else:
        spoken = ", ".join(option_phrases[:-1]) + ", or " + option_phrases[-1]

    return {
        "status": "MULTIPLE",
        "appointments": options,
        "message": f"I found these upcoming appointments: {spoken}. Which one are you referring to?",
    }


def _handle_reschedule(args: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Find new slots for rescheduling (does NOT cancel the original appointment).

    This is step 1 of the reschedule flow: discover alternative slots.
    The original appointment remains untouched until the patient picks a
    new slot and reschedule_finalize is called.

    Finalization paths (checked in order):
      1. slot_number present  → look up cached slot (most reliable)
      2. doctor_id + start_at + end_at present → forward to finalize (fallback)
    """
    call_id = get_call_id(payload)

    # -- Finalization path 1: slot_number from cache (preferred) --
    slot_number = args.get("slot_number")
    if slot_number is not None and call_id:
        cached = _pop_cached_slot(call_id, int(slot_number))
        if cached:
            finalize_args = {**args, **cached}
            if not finalize_args.get("original_appointment_id") and args.get("appointment_id"):
                finalize_args["original_appointment_id"] = args["appointment_id"]
            logger.info("reschedule: finalizing via cached slot_number=%s for call=%s", slot_number, call_id)
            return _handle_reschedule_finalize(finalize_args, payload)
        else:
            logger.warning("reschedule: slot_number=%s requested but cache miss for call=%s", slot_number, call_id)

    # -- Finalization path 2: explicit slot fields (fallback) --
    if args.get("doctor_id") and args.get("start_at") and args.get("end_at"):
        forwarded_args = dict(args)
        if not forwarded_args.get("original_appointment_id") and args.get("appointment_id"):
            forwarded_args["original_appointment_id"] = args["appointment_id"]
        return _handle_reschedule_finalize(forwarded_args, payload)

    # -- Slot discovery path --
    appointment_id = args.get("appointment_id")
    preferred_day = args.get("preferred_day", "")
    preferred_time = args.get("preferred_time", "")

    if not appointment_id:
        return {"status": "INVALID", "message": "I need to know which appointment to reschedule."}

    sb = get_supabase()

    patient_id = args.get("patient_id")

    # Fetch the original appointment
    res = (
        sb.table("appointments")
        .select("id,patient_id,specialty_id,doctor_id,status,start_at,end_at")
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
        return {"status": "INVALID", "message": "That appointment isn't active and can't be rescheduled."}

    # SAFETY: Verify the appointment has not ended yet
    end_str = appt["end_at"].replace("Z", "+00:00")
    if datetime.fromisoformat(end_str) <= now_utc():
        return {"status": "INVALID", "message": "That appointment is in the past and can't be rescheduled."}

    specialty_id = appt.get("specialty_id")
    doctor_id = appt["doctor_id"]

    # Find new slots — prefer same specialty, fall back to same doctor
    if specialty_id:
        slots = find_slots_for_specialty(specialty_id, preferred_day, preferred_time)
    else:
        slots = find_available_slots(doctor_id, preferred_day, preferred_time)
        for s in slots:
            s["doctor_id"] = doctor_id

    if not slots:
        return {
            "status": "NO_SLOTS",
            "original_appointment_id": appointment_id,
            "message": "I couldn't find any available times for rescheduling. Would you like to try a different window?",
            "slots": [],
        }

    slots = _prepare_slot_choices(slots)

    # Cache the offered slots so finalization can look them up by slot_number
    if call_id:
        _cache_slots(call_id, appointment_id, slots)

    return {
        "status": "SLOTS_AVAILABLE",
        "original_appointment_id": appointment_id,
        "slots": slots,
        "message": f"I can reschedule you to {_spoken_slot_list(slots)}. Which option works?",
    }


def _handle_reschedule_finalize(args: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """
    SAFETY-CRITICAL: Atomic-style reschedule finalization.

    Takes the original appointment ID and the selected new slot, then:
      1. Validates the original appointment is still active and reschedulable
      2. Validates the new slot is genuinely available (via slot engine)
      3. Creates the new appointment
      4. Cancels the original appointment
      5. Returns a single status response

    The original appointment is NEVER cancelled before the new one is secured.
    If the new booking succeeds but cancellation of the old one fails, a
    RESCHEDULE_PARTIAL_FAILURE status is returned so the caller can surface it.
    """
    original_appointment_id = args.get("original_appointment_id") or args.get("appointment_id")
    patient_id = args.get("patient_id")
    doctor_id = args.get("doctor_id")
    start_at = args.get("start_at")
    end_at = args.get("end_at")

    if not all([original_appointment_id, doctor_id, start_at, end_at]):
        return {"status": "INVALID", "message": "Missing required reschedule information."}

    if not isinstance(start_at, str) or not isinstance(end_at, str):
        return {"status": "INVALID", "message": "Start and end times must be valid date strings."}

    # Parse new slot times
    try:
        new_start = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
        new_end = datetime.fromisoformat(end_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return {"status": "INVALID", "message": "Could not understand the new appointment times."}

    if new_start >= new_end:
        return {"status": "INVALID", "message": "The new appointment end time must be after the start time."}

    sb = get_supabase()

    # -- Step 1: Validate original appointment is still reschedulable --
    orig_res = (
        sb.table("appointments")
        .select("id,patient_id,status,start_at,end_at,specialty_id,reason,symptoms,severity_description,severity_rating,urgency")
        .eq("id", original_appointment_id)
        .limit(1)
        .execute()
    )
    orig_data = getattr(orig_res, "data", None) or []
    if not orig_data:
        return {"status": "NOT_FOUND", "message": "I couldn't find the original appointment."}

    orig_appt = orig_data[0]

    # SECURITY: Verify the appointment belongs to the requesting patient
    if patient_id and orig_appt.get("patient_id") and orig_appt["patient_id"] != patient_id:
        return {"status": "NOT_FOUND", "message": "I couldn't find the original appointment."}

    patient_id = patient_id or orig_appt.get("patient_id")
    if not patient_id:
        return {"status": "INVALID", "message": "Missing patient information for rescheduling."}

    if orig_appt["status"] != "CONFIRMED":
        return {"status": "INVALID", "message": "The original appointment is no longer active."}

    orig_end_str = orig_appt["end_at"].replace("Z", "+00:00")
    if datetime.fromisoformat(orig_end_str) <= now_utc():
        return {"status": "INVALID", "message": "The original appointment is in the past."}

    # -- Step 2: Validate the new slot is genuinely available --
    # Exclude the original appointment from overlap checks since we intend to cancel it
    slot_rejection = validate_slot(str(doctor_id), str(start_at), str(end_at))
    if slot_rejection is not None:
        # Check if the only "overlap" is the original appointment itself
        # (edge case: rescheduling to the same doctor at a nearby time)
        if slot_rejection.get("status") == "TAKEN":
            # Re-check excluding the original appointment
            if not _check_overlap(str(doctor_id), new_start, new_end, exclude_appointment_id=str(original_appointment_id)):
                slot_rejection = None  # The only conflict was the original appointment itself
        if slot_rejection is not None:
            return slot_rejection

    vapi_call_id = get_call_id(payload)

    # -- Step 3: Create the new appointment FIRST (before cancelling the old one) --
    new_row: dict[str, Any] = {
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "start_at": start_at,
        "end_at": end_at,
        "specialty_id": args.get("specialty_id") or orig_appt.get("specialty_id"),
        "reason": args.get("reason") or orig_appt.get("reason"),
        "symptoms": orig_appt.get("symptoms"),
        "severity_description": orig_appt.get("severity_description"),
        "severity_rating": orig_appt.get("severity_rating"),
        "urgency": orig_appt.get("urgency", "ROUTINE"),
        "follow_up_from_id": None,
        "status": "CONFIRMED",
        "vapi_call_id": vapi_call_id,
    }

    try:
        insert_res = sb.table("appointments").insert(new_row).execute()
    except Exception as e:
        err_msg = str(e)
        if "unique_doctor_appointment" in err_msg or "no_overlapping_confirmed" in err_msg:
            return {
                "status": "TAKEN",
                "message": "Sorry, that time is no longer available. Please pick another slot.",
            }
        return {"status": "ERROR", "message": f"Failed to create the new appointment: {err_msg}"}

    ins = getattr(insert_res, "data", None) or []
    if not ins:
        return {"status": "ERROR", "message": "Something went wrong creating the new appointment."}

    new_appointment = ins[0]

    # -- Step 4: Cancel the original appointment ONLY after new one is confirmed --
    try:
        sb.table("appointments").update({"status": "CANCELLED"}).eq("id", original_appointment_id).execute()
    except Exception as cancel_err:
        # SAFETY: New appointment was created but old one could not be cancelled.
        # Return a clear partial-failure status so the caller/UI can surface it.
        doc_res = sb.table("doctors").select("full_name").eq("id", doctor_id).limit(1).execute()
        doc_data = getattr(doc_res, "data", None) or []
        doctor_name = doc_data[0]["full_name"] if doc_data else "your doctor"

        return {
            "status": "RESCHEDULE_PARTIAL_FAILURE",
            "new_appointment_id": new_appointment["id"],
            "original_appointment_id": original_appointment_id,
            "doctor_name": doctor_name,
            "message": (
                f"Your new appointment with {doctor_name} for "
                f"{format_for_voice(new_start)} is confirmed, but I wasn't able to "
                f"cancel your original appointment automatically. Please contact the "
                f"office to have the old appointment removed."
            ),
            "error_detail": str(cancel_err),
        }

    # -- Step 5: Success —  return unified response --
    doc_res = sb.table("doctors").select("full_name").eq("id", doctor_id).limit(1).execute()
    doc_data = getattr(doc_res, "data", None) or []
    doctor_name = doc_data[0]["full_name"] if doc_data else "your doctor"
    when = format_for_voice(new_start)

    return {
        "status": "RESCHEDULED",
        "new_appointment_id": new_appointment["id"],
        "cancelled_appointment_id": original_appointment_id,
        "doctor_name": doctor_name,
        "message": f"Done — your appointment has been rescheduled to {when} with {doctor_name}.",
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
    """Atomic-style reschedule: book new slot + cancel old appointment in one call."""
    payload = await request.json()
    return handle_tool_calls(payload, _handle_reschedule_finalize)
