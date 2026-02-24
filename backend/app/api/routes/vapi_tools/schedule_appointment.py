import json
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api.routes.vapi_tools._helpers import (
    extract_call_meta,
    extract_tool_calls,
    normalize_phone,
    parse_args,
)
from app.services.supabase_client import get_supabase

router = APIRouter()


class ScheduleAppointmentIn(BaseModel):
    full_name: str
    phone: str
    preferred_day: str
    preferred_time: str
    reason: str
    urgency: Literal["URGENT", "ROUTINE"]


def _handle_schedule(args: dict[str, Any], call_meta: dict[str, Any] | None = None) -> dict[str, Any]:
    body = ScheduleAppointmentIn(**args)

    body.phone = normalize_phone(body.phone)
    body.full_name = body.full_name.strip()
    body.reason = (body.reason or "").strip() or "routine appointment"

    appt_digits = str(uuid.uuid4().int)[:8]
    appointment_ref = f"DEMO-{appt_digits}"
    ref_spoken = f"{appt_digits[:4]} {appt_digits[4:]}"

    row: dict[str, Any] = {
        "appointment_ref": appointment_ref,
        "full_name": body.full_name,
        "phone": body.phone,  # user-provided contact phone
        "preferred_day": body.preferred_day,
        "preferred_time": body.preferred_time,
        "reason": body.reason,
        "urgency": body.urgency,
    }

    # Attach call/session metadata if available
    if call_meta:
        for k in ("vapi_call_id", "vapi_tool_call_id", "call_type", "caller_phone"):
            v = call_meta.get(k)
            if v:
                row[k] = v

    supabase = get_supabase()
    
    try:
        res = supabase.table("appointments").insert(row).execute()
        print("SUPABASE res.data:", getattr(res, "data", None))
        print("SUPABASE res.error:", getattr(res, "error", None))
    except Exception as e:
        print("SUPABASE INSERT EXCEPTION:", repr(e))
        raise
    
    inserted = res.data[0] if getattr(res, "data", None) else None
    db_id = inserted.get("id") if isinstance(inserted, dict) else None

    return {
        "appointment_id": db_id or appointment_ref,
        "appointment_ref": appointment_ref,
        "status": "CONFIRMED",
        "message": (
            f"Thanks, {body.full_name}. I've noted your appointment request for "
            f"{body.preferred_day} {body.preferred_time}. "
            f"Your reference number is DEMO {ref_spoken}."
        ),
    }


@router.post("/schedule-appointment")
async def schedule_appointment(request: Request):
    payload = await request.json()

    # print("VAPI schedule-appointment payload:\n" + json.dumps(payload, indent=2, default=str))

    call_meta = extract_call_meta(payload)

    # Allow direct calls (not tool envelope)
    if isinstance(payload, dict) and "full_name" in payload and "phone" in payload:
        return _handle_schedule(payload, call_meta)

    tool_calls = extract_tool_calls(payload)
    results: list[dict[str, Any]] = []

    for tc in tool_calls:
        tool_call_id = tc.get("id") or tc.get("toolCallId")
        args = parse_args(tc)

        try:
            out = _handle_schedule(args, call_meta)
            results.append({
                "toolCallId": tool_call_id,
                "result": json.dumps(out, separators=(",", ":")),
            })
        except Exception as e:
            err = {"status": "ERROR", "message": str(e)}
            results.append({
                "toolCallId": tool_call_id,
                "result": json.dumps(err, separators=(",", ":")),
            })

    return {"results": results}