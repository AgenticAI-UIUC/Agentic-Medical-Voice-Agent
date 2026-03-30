
"""
vapi_webhook.py handles lifecycle events from Vapi. 
When a phone call ends, Vapi sends an "end-of-call-report" containing the full transcript.
This router saves that transcript to the conversations table and links it to the right patient/appointment if possible.

"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.vapi_auth import verify_vapi_secret
from app.supabase import get_supabase


router = APIRouter(prefix="/vapi", tags=["vapi"])


@router.post("/events", dependencies=[Depends(verify_vapi_secret)])
async def vapi_events(request: Request):
    payload = await request.json()

    msg = payload.get("message") or {}
    msg_type = msg.get("type", "")
    call = payload.get("call") or msg.get("call") or {}
    call_id = call.get("id")

    # On end-of-call, save the transcript
    if msg_type == "end-of-call-report" and call_id:
        _save_conversation(call_id, msg)

    return {"ok": True}


def _save_conversation(call_id: str, msg: dict) -> None:
    transcript = msg.get("artifact", {}).get("messages") or msg.get("transcript") or []
    summary = msg.get("analysis", {}).get("summary")

    sb = get_supabase()

    # Check if conversation already exists for this call
    existing = sb.table("conversations").select("id").eq("call_id", call_id).limit(1).execute()
    existing_data = getattr(existing, "data", None) or []

    if existing_data:
        # Update existing
        sb.table("conversations").update({
            "transcript": transcript,
            "summary": summary,
        }).eq("call_id", call_id).execute()
    else:
        # Insert new — patient_id will be linked if we can find the appointment
        row = {
            "call_id": call_id,
            "transcript": transcript,
            "summary": summary,
        }

        # Try to find patient via appointment with this call_id
        appt_res = (
            sb.table("appointments")
            .select("patient_id,id")
            .eq("vapi_call_id", call_id)
            .limit(1)
            .execute()
        )
        appt_data = getattr(appt_res, "data", None) or []
        if appt_data:
            row["patient_id"] = appt_data[0]["patient_id"]

        ins = sb.table("conversations").insert(row).execute()
        ins_data = getattr(ins, "data", None) or []

        # Link conversation back to appointment
        if ins_data and appt_data:
            conv_id = ins_data[0]["id"]
            appt_id = appt_data[0]["id"]
            sb.table("appointments").update({"conversation_id": conv_id}).eq("id", appt_id).execute()
