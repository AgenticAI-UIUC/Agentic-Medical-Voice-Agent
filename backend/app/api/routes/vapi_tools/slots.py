from __future__ import annotations

import re

import json
from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel
from zoneinfo import ZoneInfo

from app.api.routes.vapi_tools._helpers import extract_tool_calls, parse_args
from app.services.doctor_service import get_default_doctor
from app.services.supabase_client import get_supabase

from datetime import datetime, timedelta, timezone
from app.services.time_nlp import (
    parse_preferred_day_to_range,
    preferred_time_bucket,
    range_to_utc_bounds,
    slot_in_bucket,
    clamp_not_in_past,
    format_voice_from_iso,
)

NEXT_AVAILABLE_ALIASES = {
    "next available day",
    "next available date",
    "next available",
    "soonest",
    "earliest",
    "earliest available",
}

SCHEDULING_HORIZON_DAYS = 14

CT = ZoneInfo("America/Chicago")

router = APIRouter()


# -------------------------
# Tool Inputs
# -------------------------

class FindSlotsIn(BaseModel):
    preferred_day: str  # today/tomorrow/Friday/...
    preferred_time: str  # morning/afternoon/...


class BookSlotIn(BaseModel):
    slot_id: str
    full_name: str
    phone: str
    reason: str = "routine appointment"
    urgency: Literal["URGENT", "ROUTINE"] = "ROUTINE"
    
def _parse_dt_loose(iso: str) -> datetime:
    s = (iso or "").strip().replace("Z", "+00:00")
    if " " in s and "T" not in s:
        s = s.replace(" ", "T", 1)
    if re.search(r"\+\d\d$", s):  # "+00" -> "+00:00"
        s = s + ":00"
    return datetime.fromisoformat(s)



# -------------------------
# Core logic
# -------------------------

def _get_single_doctor_or_raise() -> dict[str, Any]:
    doctor = get_default_doctor()
    if not doctor:
        raise RuntimeError("No active doctor found. Please create a doctor with is_active=true.")
    return doctor



from datetime import datetime, timedelta, timezone
from app.services.time_nlp import (
    parse_preferred_day_to_range,
    preferred_time_bucket,
    range_to_utc_bounds,
    slot_in_bucket,
    clamp_not_in_past,
    format_voice_from_iso,
)

NEXT_AVAILABLE_ALIASES = {
    "next available day",
    "next available date",
    "next available",
    "soonest",
    "earliest",
    "earliest available",
}


def _find_slots(args: dict[str, Any]) -> dict[str, Any]:
    body = FindSlotsIn(**args)
    doctor = _get_single_doctor_or_raise()
    doctor_id = doctor["id"]

    supabase = get_supabase()

    day_raw = (body.preferred_day or "").strip().lower()
    bucket = preferred_time_bucket(body.preferred_time)

    now_utc = datetime.now(timezone.utc)
    horizon_utc = now_utc + timedelta(days=SCHEDULING_HORIZON_DAYS)

    # -------------------------
    # Special: "next available day/date"
    # -------------------------
    if day_raw in NEXT_AVAILABLE_ALIASES:
        res = (
            supabase.table("appointment_slots")
            .select("id,start_at,end_at")
            .eq("doctor_id", doctor_id)
            .eq("status", "AVAILABLE")
            .gte("start_at", now_utc.isoformat())
            .lt("start_at", horizon_utc.isoformat())  # <-- use horizon
            .order("start_at", desc=False)
            .limit(200)
            .execute()
        )
        rows = getattr(res, "data", None) or []
        rows = [r for r in rows if clamp_not_in_past(r["start_at"]) and slot_in_bucket(r["start_at"], bucket)]

        if not rows:
            return {
                "status": "NO_SLOTS",
                "doctor_id": doctor_id,
                "doctor_name": doctor.get("full_name"),
                "message": "Sorry — I couldn’t find any available times soon. Would you like to try another time preference?",
                "slots": [],
            }

        def ct_date(iso: str):
            return _parse_dt_loose(iso).astimezone(CT).date()

        first_day = ct_date(rows[0]["start_at"])
        slots = [r for r in rows if ct_date(r["start_at"]) == first_day][:5]

    else:
        dr = parse_preferred_day_to_range(body.preferred_day)
        w_start_utc, w_end_utc = range_to_utc_bounds(dr)

        # past window
        if w_end_utc <= now_utc:
            slots = []

        # fully beyond horizon
        elif w_start_utc > horizon_utc:
            return {
                "status": "OUT_OF_RANGE",
                "doctor_id": doctor_id,
                "doctor_name": doctor.get("full_name"),
                "message": "We can only schedule up to two weeks in advance right now.",
                "slots": [],
                "horizon_days": SCHEDULING_HORIZON_DAYS,
                "suggested_preferred_days": ["this week", "next week"],
            }

        else:
            # clamp to now + horizon
            if w_start_utc < now_utc:
                w_start_utc = now_utc
            if w_end_utc > horizon_utc:
                w_end_utc = horizon_utc  # <-- clamp end

            res = (
                supabase.table("appointment_slots")
                .select("id,start_at,end_at")
                .eq("doctor_id", doctor_id)
                .eq("status", "AVAILABLE")
                .gte("start_at", w_start_utc.isoformat())
                .lt("start_at", w_end_utc.isoformat())
                .order("start_at", desc=False)
                .limit(200)
                .execute()
            )
            rows = getattr(res, "data", None) or []
            rows = [r for r in rows if clamp_not_in_past(r["start_at"]) and slot_in_bucket(r["start_at"], bucket)]
            slots = rows[:5]

    if not slots:
        return {
            "status": "NO_SLOTS",
            "doctor_id": doctor_id,
            "doctor_name": doctor.get("full_name"),
            "message": "Sorry — I couldn’t find any available times then. Would you like to try another day or time?",
            "slots": [],
        }

    choices = [
        {
            "slot_id": s["id"],
            "start_at": s["start_at"],
            "end_at": s["end_at"],
            "label": format_voice_from_iso(s["start_at"]),
        }
        for s in slots
    ]

    top_labels = [c["label"] for c in choices[:3]]
    spoken = top_labels[0] if len(top_labels) == 1 else ", ".join(top_labels[:-1]) + " or " + top_labels[-1]

    return {
        "status": "OK",
        "doctor_id": doctor_id,
        "doctor_name": doctor.get("full_name"),
        "slots": choices,
        "message": f"I have {spoken}. Which one works best?",
    }
    
    
def _book_slot(args: dict[str, Any]) -> dict[str, Any]:
    body = BookSlotIn(**args)
    doctor = _get_single_doctor_or_raise()
    doctor_id = doctor["id"]

    supabase = get_supabase()

    # 1) Atomically claim the slot (only if still AVAILABLE AND belongs to our doctor)
    upd = (
        supabase.table("appointment_slots")
        .update({"status": "BOOKED"})
        .eq("id", body.slot_id)
        .eq("doctor_id", doctor_id)
        .eq("status", "AVAILABLE")
        .execute()
    )

    updated_rows = getattr(upd, "data", None) or []
    if not updated_rows:
        return {
            "status": "TAKEN",
            "message": "Sorry — that time was just booked. Would you like to pick another time?",
        }

    # 1b) Re-fetch slot details (reliable across client versions)
    slot_res = (
        supabase.table("appointment_slots")
        .select("id,doctor_id,start_at,end_at,status")
        .eq("id", body.slot_id)
        .limit(1)
        .execute()
    )
    slot_data = getattr(slot_res, "data", None) or []
    if not slot_data:
        # Extremely unlikely: updated but can't read back
        raise RuntimeError("Booked slot but could not retrieve slot details.")

    slot = slot_data[0]

    # 2) Insert appointment (NO .select() chaining to satisfy Pyright)
    appt_row: dict[str, Any] = {
        "full_name": body.full_name.strip(),
        "phone": body.phone,
        "reason": (body.reason or "routine appointment").strip() or "routine appointment",
        "urgency": body.urgency,
        "doctor_id": doctor_id,
        "slot_id": slot["id"],
        # optional placeholders
        "preferred_day": "CONFIRMED",
        "preferred_time": "CONFIRMED",
    }

    try:
        ins = supabase.table("appointments").insert(appt_row).execute()
    except Exception as e:
        # rollback slot if appointment insert fails
        supabase.table("appointment_slots").update({"status": "AVAILABLE"}).eq("id", body.slot_id).execute()
        raise RuntimeError(f"Failed to create appointment: {e}") from e

    ins_data = getattr(ins, "data", None) or []
    appt_id = ins_data[0].get("id") if ins_data and isinstance(ins_data[0], dict) else None

    # Fallback: fetch appointment id if insert didn't return rows
    if not appt_id:
        appt_fetch = (
            supabase.table("appointments")
            .select("id")
            .eq("slot_id", body.slot_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        fetch_data = getattr(appt_fetch, "data", None) or []
        appt_id = fetch_data[0]["id"] if fetch_data else None

    # 3) Link slot -> appointment_id
    if appt_id:
        supabase.table("appointment_slots").update({"appointment_id": appt_id}).eq("id", body.slot_id).execute()

    when = format_voice_from_iso(slot["start_at"])
    return {
        "status": "CONFIRMED",
        "appointment_id": appt_id,
        "slot_id": slot["id"],
        "doctor_name": doctor.get("full_name"),
        "message": f"All set — you’re booked with {doctor.get('full_name')} for {when}.",
    }
# -------------------------
# Vapi tool endpoints
# -------------------------

@router.post("/find-available-slots")
async def find_available_slots(request: Request):
    payload = await request.json()
    tool_calls = extract_tool_calls(payload)

    results: list[dict[str, Any]] = []

    for tc in tool_calls:
        tool_call_id = tc.get("id") or tc.get("toolCallId")
        args = parse_args(tc)
        try:
            out = _find_slots(args)
            results.append({"toolCallId": tool_call_id, "result": json.dumps(out, separators=(",", ":"))})
        except Exception as e:
            err = {"status": "ERROR", "message": str(e)}
            results.append({"toolCallId": tool_call_id, "result": json.dumps(err, separators=(",", ":"))})

    return {"results": results}


@router.post("/book-slot")
async def book_slot(request: Request):
    payload = await request.json()
    tool_calls = extract_tool_calls(payload)

    results: list[dict[str, Any]] = []

    for tc in tool_calls:
        tool_call_id = tc.get("id") or tc.get("toolCallId")
        args = parse_args(tc)
        try:
            out = _book_slot(args)
            results.append({"toolCallId": tool_call_id, "result": json.dumps(out, separators=(",", ":"))})
        except Exception as e:
            err = {"status": "ERROR", "message": str(e)}
            results.append({"toolCallId": tool_call_id, "result": json.dumps(err, separators=(",", ":"))})

    return {"results": results}