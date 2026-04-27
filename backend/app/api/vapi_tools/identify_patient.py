from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.api.vapi_helpers import handle_tool_calls, normalize_phone
from app.supabase import get_supabase

router = APIRouter()


_WORD_TO_DIGIT = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "oh": "0",
    "o": "0",
}


def _normalize_uin(raw: str) -> str:
    """Convert spoken UIN like 'one two three ...' or '1-2-3-...' to pure digits."""
    import re

    raw = raw.strip().lower()
    # Replace word digits with numeric digits
    for word, digit in _WORD_TO_DIGIT.items():
        raw = re.sub(rf"\b{word}\b", digit, raw)
    # Strip everything that isn't a digit
    return re.sub(r"\D", "", raw)


def _invalid_uin_result(uin: str, *, action: str) -> dict[str, Any]:
    if not uin:
        return {
            "status": "INVALID",
            "reason": "MISSING_UIN",
            "message": "I didn't catch your UIN. Could you repeat it?",
        }

    received_digits = len(uin)
    return {
        "status": "INVALID",
        "reason": "WRONG_LENGTH",
        "expected_digits": 9,
        "received_digits": received_digits,
        "message": (
            f"I heard {received_digits} digits, but I need your 9-digit university UIN to {action}."
        ),
    }


def _lookup_patient(args: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    uin = _normalize_uin(args.get("uin") or "")
    if not uin:
        return _invalid_uin_result(uin, action="look up your record")
    if len(uin) != 9 or not uin.isdigit():
        return _invalid_uin_result(uin, action="look up your record")

    sb = get_supabase()
    res = (
        sb.table("patients")
        .select("id,uin,full_name,phone,email,allergies")
        .eq("uin", uin)
        .limit(1)
        .execute()
    )
    data = getattr(res, "data", None) or []

    if not data:
        return {
            "status": "NOT_FOUND",
            "uin_searched": uin,
            "message": (
                f"No patient record found for UIN {uin}. "
                "This is not an error — the UIN simply does not exist in our system yet. "
                "The patient may need to be registered as a new patient."
            ),
        }

    patient = data[0]
    return {
        "status": "FOUND",
        "patient_id": patient["id"],
        "uin": patient["uin"],
        "full_name": patient["full_name"],
        "message": f"I found your record. You're {patient['full_name']}, is that correct?",
    }


def _register_patient(args: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    uin = _normalize_uin(args.get("uin") or "")
    full_name = (args.get("full_name") or "").strip()
    phone = normalize_phone(args.get("phone") or "")

    if not uin or len(uin) != 9 or not uin.isdigit():
        return _invalid_uin_result(uin, action="register you")
    if not full_name:
        return {
            "status": "INVALID",
            "message": "I need your full name to register you.",
        }
    if not phone:
        return {
            "status": "INVALID",
            "message": "I need a valid phone number to register you.",
        }

    sb = get_supabase()

    # Check if UIN already exists
    existing_uin = (
        sb.table("patients")
        .select("id,uin,full_name")
        .eq("uin", uin)
        .limit(1)
        .execute()
    )
    existing_uin_data = getattr(existing_uin, "data", None) or []
    if existing_uin_data:
        p = existing_uin_data[0]
        return {
            "status": "ALREADY_EXISTS",
            "patient_id": p["id"],
            "uin": p["uin"],
            "full_name": p["full_name"],
            "message": f"It looks like you're already registered as {p['full_name']}.",
        }

    row = {
        "uin": uin,
        "full_name": full_name,
        "phone": phone,
        "email": (args.get("email") or "").strip() or None,
        "allergies": (args.get("allergies") or "").strip() or None,
    }

    res = sb.table("patients").insert(row).execute()
    ins = getattr(res, "data", None) or []
    if not ins:
        return {
            "status": "ERROR",
            "message": "Something went wrong during registration. Please try again.",
        }

    patient = ins[0]
    return {
        "status": "REGISTERED",
        "patient_id": patient["id"],
        "uin": uin,
        "full_name": full_name,
        "message": f"Registration complete for {full_name}.",
    }


@router.post("/identify-patient")
async def identify_patient(request: Request):
    payload = await request.json()
    return handle_tool_calls(payload, _lookup_patient)


@router.post("/register-patient")
async def register_patient(request: Request):
    payload = await request.json()
    return handle_tool_calls(payload, _register_patient)
