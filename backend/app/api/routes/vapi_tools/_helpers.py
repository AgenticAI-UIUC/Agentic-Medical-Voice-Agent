import json
import re
from typing import Any


def extract_tool_calls(payload: dict[str, Any]) -> list[dict[str, Any]]:
    msg = payload.get("message", {})
    return (
        payload.get("toolCalls")
        or msg.get("toolCalls")
        or msg.get("toolCallList")
        or []
    )


def extract_call_meta(payload: dict[str, Any]) -> dict[str, Any]:
    message = payload.get("message") or {}

    call = payload.get("call") or message.get("call") or {}
    customer = (
        payload.get("customer")
        or message.get("customer")
        or call.get("customer")
        or {}
    )

    tool_calls = extract_tool_calls(payload)
    tool_call_id = tool_calls[0].get("id") if tool_calls else None

    return {
        "vapi_call_id": call.get("id"),
        "vapi_tool_call_id": tool_call_id,
        "call_type": call.get("type"),
        "caller_phone": customer.get("number"),
    }


def parse_args(tc: dict[str, Any]) -> dict[str, Any]:
    fn = tc.get("function") or {}
    args = fn.get("arguments") or {}
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return {}
    return args if isinstance(args, dict) else {}


def normalize_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")