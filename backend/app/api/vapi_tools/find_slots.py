from __future__ import annotations

import logging
import time as _time
from threading import Lock
from typing import Any

from fastapi import APIRouter, Request

from app.api.vapi_helpers import get_call_id, handle_tool_calls
from app.services.slot_engine import find_slots_for_specialty, find_available_slots

logger = logging.getLogger(__name__)

router = APIRouter()
MAX_VOICE_OPTIONS = 3

# ---------------------------------------------------------------------------
# Lightweight in-memory slot cache keyed by VAPI call_id.
#
# When find_slots offers slots to the caller, it caches them here so that the
# book tool can look up the *exact* slot the patient chose by slot_number —
# eliminating the risk of VAPI's LLM passing the wrong doctor_id.
# ---------------------------------------------------------------------------
_slot_cache: dict[str, dict[str, Any]] = {}
_cache_lock = Lock()
_CACHE_TTL_SECONDS = 600  # 10 minutes


def cache_slots(call_id: str, slots: list[dict[str, Any]]) -> None:
    with _cache_lock:
        _slot_cache[call_id] = {
            "slots": slots,
            "expires": _time.monotonic() + _CACHE_TTL_SECONDS,
        }
        now = _time.monotonic()
        expired = [k for k, v in _slot_cache.items() if v["expires"] < now]
        for k in expired:
            del _slot_cache[k]


def pop_cached_slot(call_id: str, slot_number: int) -> dict[str, Any] | None:
    """Look up a previously offered slot by call_id + slot_number."""
    with _cache_lock:
        entry = _slot_cache.get(call_id)
        if not entry or entry["expires"] < _time.monotonic():
            return None
        for slot in entry["slots"]:
            if slot.get("slot_number") == slot_number:
                return dict(slot)
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


def _handle_find_slots(args: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    call_id = get_call_id(payload)
    specialty_id = args.get("specialty_id")
    doctor_id = args.get("doctor_id")
    preferred_day = args.get("preferred_day", "")
    preferred_time = args.get("preferred_time", "")

    if doctor_id:
        # Direct doctor lookup (e.g. follow-up with same doctor)
        slots = _prepare_slot_choices(find_available_slots(doctor_id, preferred_day, preferred_time))
        if not slots:
            return {
                "status": "NO_SLOTS",
                "message": "I couldn't find any available times for that doctor in that window. Would you like to try a different time?",
                "slots": [],
            }

        if call_id:
            cache_slots(call_id, slots)

        return {
            "status": "OK",
            "slots": slots,
            "message": f"I have {_spoken_slot_list(slots)}. Which option works best?",
        }

    if not specialty_id:
        return {
            "status": "INVALID",
            "message": "I need to know the specialty to search for available times.",
            "slots": [],
        }

    slots = _prepare_slot_choices(find_slots_for_specialty(specialty_id, preferred_day, preferred_time))
    if not slots:
        return {
            "status": "NO_SLOTS",
            "message": "I couldn't find any available times in that window. Would you like to try a different time or look further out?",
            "slots": [],
        }

    if call_id:
        cache_slots(call_id, slots)

    return {
        "status": "OK",
        "slots": slots,
        "message": f"I found these options: {_spoken_slot_list(slots)}. Which option works best?",
    }


@router.post("/find-slots")
async def find_slots(request: Request):
    payload = await request.json()
    return handle_tool_calls(payload, _handle_find_slots)
