from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.api.vapi_helpers import handle_tool_calls
from app.services.slot_engine import find_slots_for_specialty, find_available_slots, is_next_available_request
from app.services.time_utils import parse_time_bucket

router = APIRouter()


def _should_retry_with_any(preferred_day: str, preferred_time: str) -> bool:
    return is_next_available_request(preferred_day) and parse_time_bucket(preferred_time) != "any"


def _join_labels(labels: list[str]) -> str:
    return labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " or " + labels[-1]


def _collapse_same_day_labels(labels: list[str]) -> tuple[str, bool]:
    parsed = [label.rsplit(" at ", 1) for label in labels]
    if any(len(parts) != 2 for parts in parsed):
        return _join_labels(labels), False

    date_parts = [parts[0] for parts in parsed]
    time_parts = [parts[1] for parts in parsed]
    if len(set(date_parts)) != 1:
        return _join_labels(labels), False

    return f"{date_parts[0]} at {_join_labels(time_parts)}", True


def _format_slot_options(slots: list[dict[str, Any]], include_doctor: bool) -> str:
    visible_slots = slots[:3]
    labels = [slot["label"] for slot in visible_slots]
    spoken_labels, collapsed_same_day = _collapse_same_day_labels(labels)
    if not include_doctor:
        return spoken_labels

    doctor_names = {slot.get("doctor_name") for slot in visible_slots}
    if len(doctor_names) == 1:
        doctor_name = visible_slots[0].get("doctor_name")
        if doctor_name:
            if collapsed_same_day:
                return f"with {doctor_name} on {spoken_labels}"
            return f"with {doctor_name}: {spoken_labels}"

    detailed_labels = [f"{slot['label']} with {slot['doctor_name']}" for slot in visible_slots]
    return _join_labels(detailed_labels)


def _relaxed_message(preferred_time: str, slots: list[dict[str, Any]], include_doctor: bool) -> str:
    spoken = _format_slot_options(slots, include_doctor)
    bucket = parse_time_bucket(preferred_time)
    bucket_text = "morning" if bucket == "morning" else "afternoon"
    return (
        f"I don't see any {bucket_text} openings as soon as possible, "
        f"but the earliest appointments I do have are {spoken}. Which one works best?"
    )

def _handle_find_slots(args: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    specialty_id = args.get("specialty_id")
    doctor_id = args.get("doctor_id")
    preferred_day = args.get("preferred_day", "")
    preferred_time = args.get("preferred_time", "")

    if doctor_id:
        # Direct doctor lookup (e.g. follow-up with same doctor)
        slots = find_available_slots(doctor_id, preferred_day, preferred_time)
        if not slots and _should_retry_with_any(preferred_day, preferred_time):
            slots = find_available_slots(doctor_id, preferred_day, "any")
            if slots:
                return {
                    "status": "OK",
                    "slots": slots,
                    "message": _relaxed_message(preferred_time, slots, include_doctor=False),
                }
        if not slots:
            return {
                "status": "NO_SLOTS",
                "message": "I couldn't find any available times for that doctor in that window. Would you like to try a different time?",
                "slots": [],
            }

        spoken = _format_slot_options(slots, include_doctor=False)
        return {
            "status": "OK",
            "slots": slots,
            "message": f"I have {spoken}. Which one works best?",
        }

    if not specialty_id:
        return {
            "status": "INVALID",
            "message": "I need to know the specialty to search for available times.",
            "slots": [],
        }

    slots = find_slots_for_specialty(specialty_id, preferred_day, preferred_time)
    if not slots and _should_retry_with_any(preferred_day, preferred_time):
        slots = find_slots_for_specialty(specialty_id, preferred_day, "any")
        if slots:
            return {
                "status": "OK",
                "slots": slots,
                "message": _relaxed_message(preferred_time, slots, include_doctor=True),
            }
    if not slots:
        return {
            "status": "NO_SLOTS",
            "message": "I couldn't find any available times in that window. Would you like to try a different time or look further out?",
            "slots": [],
        }

    spoken = _format_slot_options(slots, include_doctor=True)
    return {
        "status": "OK",
        "slots": slots,
        "message": f"I found these options: {spoken}. Which one works best?",
    }


@router.post("/find-slots")
async def find_slots(request: Request):
    payload = await request.json()
    return handle_tool_calls(payload, _handle_find_slots)
