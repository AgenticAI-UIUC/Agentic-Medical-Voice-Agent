from __future__ import annotations

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
            results.append(vapi_tool_response(tc_id, {"status": "ERROR", "message": str(e)}))

    return {"results": results}
