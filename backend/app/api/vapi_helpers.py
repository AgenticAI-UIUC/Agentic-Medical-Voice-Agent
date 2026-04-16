from __future__ import annotations

import json
import re
import uuid
from typing import Any

import httpx


def _tool_error_result(exc: Exception) -> dict[str, str]:
    if isinstance(exc, httpx.TimeoutException):
        return {
            "status": "ERROR",
            "message": "I'm having trouble reaching the clinic records system right now. Please try again in a moment.",
        }
    return {"status": "ERROR", "message": str(exc)}


def extract_tool_calls(payload: dict[str, Any]) -> list[dict[str, Any]]:
    msg = payload.get("message", {})
    return (
        payload.get("toolCalls")
        or msg.get("toolCalls")
        or msg.get("toolCallList")
        or []
    )


def parse_args(tc: dict[str, Any]) -> dict[str, Any]:
    fn = tc.get("function") or {}
    args = fn.get("arguments") or {}
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return {}
    return args if isinstance(args, dict) else {}


def get_tool_call_id(tc: dict[str, Any]) -> str | None:
    return tc.get("id") or tc.get("toolCallId")


def get_call_id(payload: dict[str, Any]) -> str | None:
    msg = payload.get("message") or {}
    call = payload.get("call") or msg.get("call") or {}
    return call.get("id")


def normalize_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def coerce_string(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off", ""}:
            return False
    return False


def coerce_optional_int(
    value: Any,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int | None:
    if value is None or isinstance(value, bool):
        return None

    candidate: int
    if isinstance(value, int):
        candidate = value
    elif isinstance(value, float):
        if not value.is_integer():
            return None
        candidate = int(value)
    elif isinstance(value, str):
        normalized = value.strip()
        if not re.fullmatch(r"[+-]?\d+", normalized):
            return None
        candidate = int(normalized)
    else:
        return None

    if minimum is not None and candidate < minimum:
        return None
    if maximum is not None and candidate > maximum:
        return None
    return candidate


def coerce_allowed_string(
    value: Any,
    allowed: set[str],
    *,
    default: str | None = None,
) -> str | None:
    normalized = coerce_string(value).upper()
    if not normalized:
        return default
    return normalized if normalized in allowed else default


def is_valid_uuid(value: Any) -> bool:
    normalized = coerce_string(value)
    if not normalized:
        return False
    try:
        uuid.UUID(normalized)
        return True
    except (ValueError, AttributeError):
        return False


def vapi_tool_response(tool_call_id: str | None, result: dict[str, Any]) -> dict[str, Any]:
    """Build a single tool result in Vapi's expected format."""
    return {
        "toolCallId": tool_call_id,
        "result": json.dumps(result, separators=(",", ":")),
    }


def handle_tool_calls(payload: dict[str, Any], handler) -> dict[str, Any]:
    """
    Generic wrapper: extract tool calls from Vapi payload, run handler
    on each, return {"results": [...]}.
    """
    tool_calls = extract_tool_calls(payload)
    results = []

    for tc in tool_calls:
        tc_id = get_tool_call_id(tc)
        args = parse_args(tc)
        try:
            out = handler(args, payload)
            results.append(vapi_tool_response(tc_id, out))
        except Exception as e:
            results.append(vapi_tool_response(tc_id, _tool_error_result(e)))

    return {"results": results}
