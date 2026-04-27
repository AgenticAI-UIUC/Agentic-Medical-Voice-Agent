"""
vapi_webhook.py handles lifecycle events from Vapi.

The dashboard depends on this router for both live observability and the final
call record. During a call, Vapi can send status, transcript, and conversation
updates. At the end, it sends an "end-of-call-report" with the final transcript
and analysis. This router stores all of those events in the conversations table
and links the row to any appointment created by the call.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.config import settings
from app.supabase import get_supabase


router = APIRouter(prefix="/vapi", tags=["vapi"])


def _verify_secret(request: Request) -> None:
    if not settings.VAPI_WEBHOOK_SECRET:
        return
    token = request.headers.get("x-vapi-secret")
    if token != settings.VAPI_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/events")
async def vapi_events(request: Request):
    _verify_secret(request)
    payload = await request.json()

    msg = _get_message(payload)
    msg_type = str(msg.get("type") or "")
    call_id = _get_call_id(payload, msg)

    if not call_id:
        return {"ok": True}

    if msg_type == "end-of-call-report":
        _save_conversation(call_id, msg)
    elif msg_type == "status-update":
        _save_status_update(call_id, msg)
    elif msg_type == "conversation-update":
        _save_conversation_update(call_id, msg)
    elif msg_type == "transcript" or msg_type.startswith("transcript["):
        _save_transcript_update(call_id, msg, msg_type)

    return {"ok": True}


def _get_message(payload: dict[str, Any]) -> dict[str, Any]:
    message = payload.get("message")
    return message if isinstance(message, dict) else {}


def _get_call(payload: dict[str, Any], msg: dict[str, Any]) -> dict[str, Any]:
    call = payload.get("call") or msg.get("call")
    return call if isinstance(call, dict) else {}


def _get_call_id(payload: dict[str, Any], msg: dict[str, Any]) -> str | None:
    call = _get_call(payload, msg)
    call_id = (
        call.get("id")
        or msg.get("callId")
        or msg.get("call_id")
        or payload.get("callId")
        or payload.get("call_id")
    )
    return str(call_id) if call_id else None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coerce_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value).strip()
    return text or None


_PUBLIC_TRANSCRIPT_ROLES = {
    "assistant",
    "bot",
    "customer",
    "human",
    "message",
    "transcript",
    "user",
}


def _message_text(message: dict[str, Any]) -> str:
    for key in ("message", "transcript", "content", "text"):
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _sanitize_transcript(transcript: Any) -> Any:
    if not isinstance(transcript, list):
        return transcript

    safe_messages: list[Any] = []
    for item in transcript:
        if isinstance(item, str):
            if item.strip():
                safe_messages.append(item)
            continue

        if not isinstance(item, dict):
            continue

        role = str(item.get("role") or item.get("speaker") or "message").strip().lower()
        if role not in _PUBLIC_TRANSCRIPT_ROLES:
            continue

        if not _message_text(item):
            continue

        safe_messages.append(item)

    return safe_messages


def _extract_full_transcript(msg: dict[str, Any]) -> Any:
    artifact = msg.get("artifact")
    artifact = artifact if isinstance(artifact, dict) else {}

    messages = artifact.get("messages")
    if isinstance(messages, list):
        sanitized_messages = _sanitize_transcript(messages)
        if sanitized_messages:
            return sanitized_messages

    transcript = artifact.get("transcript")
    if transcript is not None:
        return _sanitize_transcript(transcript)

    transcript = msg.get("transcript")
    return _sanitize_transcript(transcript) if transcript is not None else []


def _extract_summary(msg: dict[str, Any]) -> str | None:
    analysis = msg.get("analysis")
    analysis = analysis if isinstance(analysis, dict) else {}
    summary = analysis.get("summary") or msg.get("summary")
    return str(summary) if summary else None


def _extract_outcome(msg: dict[str, Any]) -> str | None:
    analysis = msg.get("analysis")
    analysis = analysis if isinstance(analysis, dict) else {}

    for key in ("successEvaluation", "success_evaluation", "outcome", "result"):
        value = analysis.get(key)
        if value:
            return str(value)

    structured_data = analysis.get("structuredData") or analysis.get("structured_data")
    if isinstance(structured_data, dict):
        for key in ("outcome", "call_outcome", "result", "status"):
            value = structured_data.get(key)
            if value:
                return str(value)

    ended_reason = msg.get("endedReason") or msg.get("ended_reason")
    return str(ended_reason) if ended_reason else None


def _extract_transcript_type(msg: dict[str, Any], msg_type: str) -> str:
    transcript_type = str(msg.get("transcriptType") or "").strip().lower()
    if transcript_type:
        return transcript_type
    if "final" in msg_type:
        return "final"
    if "partial" in msg_type:
        return "partial"
    return "final"


def _merge_transcript_event(
    existing: Any,
    msg: dict[str, Any],
    msg_type: str,
) -> list[dict[str, Any]]:
    existing = _sanitize_transcript(existing)
    messages = list(existing) if isinstance(existing, list) else []

    text = msg.get("transcript") or msg.get("message") or msg.get("content")
    text = str(text).strip() if text else ""
    if not text:
        return messages

    transcript_type = _extract_transcript_type(msg, msg_type)
    role = str(msg.get("role") or "user")
    entry: dict[str, Any] = {
        "role": role,
        "message": text,
        "transcript_type": transcript_type,
    }

    for source_key, target_key in (
        ("time", "time"),
        ("endTime", "endTime"),
        ("secondsFromStart", "secondsFromStart"),
        ("duration", "duration"),
        ("isFiltered", "isFiltered"),
        ("detectedThreats", "detectedThreats"),
        ("originalTranscript", "originalTranscript"),
    ):
        if source_key in msg:
            entry[target_key] = msg[source_key]

    if transcript_type == "partial":
        if (
            messages
            and isinstance(messages[-1], dict)
            and messages[-1].get("role") == role
            and messages[-1].get("transcript_type") == "partial"
        ):
            messages[-1] = entry
        else:
            messages.append(entry)
        return messages

    if (
        messages
        and isinstance(messages[-1], dict)
        and messages[-1].get("role") == role
        and messages[-1].get("transcript_type") == "partial"
    ):
        messages.pop()

    if not (
        messages
        and isinstance(messages[-1], dict)
        and messages[-1].get("role") == role
        and messages[-1].get("message") == text
    ):
        messages.append(entry)

    return messages


def _find_appointment_for_call(sb: Any, call_id: str) -> dict[str, Any] | None:
    appt_res = (
        sb.table("appointments")
        .select("patient_id,id")
        .eq("vapi_call_id", call_id)
        .limit(1)
        .execute()
    )
    appt_data = getattr(appt_res, "data", None) or []
    if not appt_data:
        return None
    appointment = appt_data[0]
    return appointment if isinstance(appointment, dict) else None


def _upsert_conversation(
    call_id: str,
    updates: dict[str, Any],
    *,
    transcript: Any | None = None,
    link_appointment: bool = True,
) -> None:
    updates = {key: value for key, value in updates.items() if value is not None}
    if transcript is not None:
        updates["transcript"] = _sanitize_transcript(transcript)

    sb = get_supabase()

    existing = (
        sb.table("conversations")
        .select("id,patient_id,transcript")
        .eq("call_id", call_id)
        .limit(1)
        .execute()
    )
    existing_data = getattr(existing, "data", None) or []

    appointment = _find_appointment_for_call(sb, call_id) if link_appointment else None
    if appointment and appointment.get("patient_id"):
        updates["patient_id"] = appointment["patient_id"]

    if existing_data:
        conversation_id = existing_data[0]["id"]
        sb.table("conversations").update(updates).eq("call_id", call_id).execute()
    else:
        row = {
            "call_id": call_id,
            "transcript": updates.get("transcript", []),
            **updates,
        }
        ins = sb.table("conversations").insert(row).execute()
        ins_data = getattr(ins, "data", None) or []
        conversation_id = ins_data[0]["id"] if ins_data else None

    if conversation_id and appointment:
        sb.table("appointments").update({"conversation_id": conversation_id}).eq(
            "id",
            appointment["id"],
        ).execute()


def _save_status_update(call_id: str, msg: dict[str, Any]) -> None:
    call = _get_call({}, msg)
    status = str(msg.get("status") or call.get("status") or "unknown")
    now = _now_iso()
    updates: dict[str, Any] = {
        "call_status": status,
        "last_event_at": now,
    }

    if status == "in-progress":
        updates["started_at"] = _coerce_iso(call.get("startedAt")) or now
    elif status == "ended":
        updates["ended_at"] = _coerce_iso(call.get("endedAt")) or now

    _upsert_conversation(call_id, updates)


def _save_conversation_update(call_id: str, msg: dict[str, Any]) -> None:
    messages = msg.get("messages")
    if not isinstance(messages, list):
        messages = msg.get("messagesOpenAIFormatted")
    _upsert_conversation(
        call_id,
        {
            "call_status": "in-progress",
            "last_event_at": _now_iso(),
        },
        transcript=_sanitize_transcript(messages) if isinstance(messages, list) else None,
    )


def _save_transcript_update(call_id: str, msg: dict[str, Any], msg_type: str) -> None:
    sb = get_supabase()
    existing = (
        sb.table("conversations")
        .select("id,transcript")
        .eq("call_id", call_id)
        .limit(1)
        .execute()
    )
    existing_data = getattr(existing, "data", None) or []
    current_transcript = existing_data[0].get("transcript") if existing_data else []
    transcript = _merge_transcript_event(current_transcript, msg, msg_type)

    updates = {
        "call_status": "in-progress",
        "last_event_at": _now_iso(),
    }

    if existing_data:
        appointment = _find_appointment_for_call(sb, call_id)
        if appointment and appointment.get("patient_id"):
            updates["patient_id"] = appointment["patient_id"]
        conversation_id = existing_data[0]["id"]
        sb.table("conversations").update(
            {
                **updates,
                "transcript": transcript,
            }
        ).eq("call_id", call_id).execute()
        if appointment:
            sb.table("appointments").update({"conversation_id": conversation_id}).eq(
                "id",
                appointment["id"],
            ).execute()
        return

    _upsert_conversation(call_id, updates, transcript=transcript)


def _save_conversation(call_id: str, msg: dict[str, Any]) -> None:
    call = _get_call({}, msg)
    now = _now_iso()
    _upsert_conversation(
        call_id,
        {
            "summary": _extract_summary(msg),
            "call_status": "ended",
            "outcome": _extract_outcome(msg),
            "ended_reason": msg.get("endedReason") or msg.get("ended_reason"),
            "started_at": _coerce_iso(call.get("startedAt")),
            "ended_at": _coerce_iso(call.get("endedAt")) or now,
            "last_event_at": now,
        },
        transcript=_extract_full_transcript(msg),
    )
