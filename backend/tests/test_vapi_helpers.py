from __future__ import annotations

import json

import httpx
import pytest

from app.api import vapi_helpers


def test_extract_tool_calls_prefers_top_level_payload() -> None:
    payload = {
        "toolCalls": [{"id": "top"}],
        "message": {"toolCalls": [{"id": "nested"}]},
    }

    assert vapi_helpers.extract_tool_calls(payload) == [{"id": "top"}]


def test_extract_tool_calls_supports_tool_call_list_fallback() -> None:
    payload = {"message": {"toolCallList": [{"id": "legacy"}]}}

    assert vapi_helpers.extract_tool_calls(payload) == [{"id": "legacy"}]


def test_parse_args_accepts_dicts_and_json_strings() -> None:
    direct = {"function": {"arguments": {"patient_id": "p-1"}}}
    encoded = {"function": {"arguments": json.dumps({"patient_id": "p-2"})}}
    invalid = {"function": {"arguments": "{not json}"}}

    assert vapi_helpers.parse_args(direct) == {"patient_id": "p-1"}
    assert vapi_helpers.parse_args(encoded) == {"patient_id": "p-2"}
    assert vapi_helpers.parse_args(invalid) == {}


def test_get_call_id_and_normalize_phone() -> None:
    payload = {"message": {"call": {"id": "call-123"}}}

    assert vapi_helpers.get_call_id(payload) == "call-123"
    assert vapi_helpers.normalize_phone("(217) 555-1212") == "2175551212"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("7", 7),
        ("seven", 7),
        ("I would say 6 out of 10", 6),
        ("mild", 2),
        ("not too bad", 5),
        ("moderate", 5),
        ("manageable", 5),
        ("very bad", 8),
        ("really bad", 8),
        ("the worst I've felt", 10),
        ("unbearable", 10),
        ("unclear", None),
        ("11", None),
    ],
)
def test_coerce_severity_rating_accepts_numeric_and_qualitative_answers(
    value: str,
    expected: int | None,
) -> None:
    assert vapi_helpers.coerce_severity_rating(value) == expected


def test_handle_tool_calls_wraps_results_and_errors() -> None:
    payload = {
        "toolCalls": [
            {"id": "ok", "function": {"arguments": {"value": 1}}},
            {"id": "bad", "function": {"arguments": {"value": 2}}},
        ]
    }

    def handler(args: dict[str, int], payload: dict[str, object]) -> dict[str, object]:
        if args["value"] == 2:
            raise RuntimeError("boom")
        return {"status": "OK", "value": args["value"]}

    response = vapi_helpers.handle_tool_calls(payload, handler)

    assert response["results"][0]["toolCallId"] == "ok"
    assert json.loads(response["results"][0]["result"]) == {"status": "OK", "value": 1}
    assert response["results"][1]["toolCallId"] == "bad"
    assert json.loads(response["results"][1]["result"]) == {
        "status": "ERROR",
        "message": "boom",
    }


def test_handle_tool_calls_maps_timeouts_to_friendly_error() -> None:
    payload = {
        "toolCalls": [
            {"id": "slow", "function": {"arguments": {"value": 1}}},
        ]
    }

    def handler(args: dict[str, int], payload: dict[str, object]) -> dict[str, object]:
        raise httpx.ReadTimeout("timed out")

    response = vapi_helpers.handle_tool_calls(payload, handler)

    assert response["results"][0]["toolCallId"] == "slow"
    assert json.loads(response["results"][0]["result"]) == {
        "status": "ERROR",
        "message": "I'm having trouble reaching the clinic records system right now. Please try again in a moment.",
    }
