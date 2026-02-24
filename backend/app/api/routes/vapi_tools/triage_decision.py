import json
from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api.routes.vapi_tools._helpers import (
    extract_tool_calls,
    parse_args,
)

router = APIRouter()

RedFlag = Literal[
    "trouble_breathing",
    "chest_pain_or_pressure",
    "fainting",
    "confusion",
    "stroke_signs",
    "heavy_bleeding",
    "severe_allergic_reaction",
]


class TriageDecisionIn(BaseModel):
    symptom: str
    duration: str
    trend: Literal["worse", "same", "better", "unsure"] = "unsure"
    red_flags: list[RedFlag] = []


def _handle_triage(args: dict[str, Any]) -> dict[str, Any]:
    body = TriageDecisionIn(**args)
    symptom = body.symptom.lower()

    if body.red_flags or "chest" in symptom or "can't breathe" in symptom or "shortness of breath" in symptom:
        return {
            "outcome": "ER",
            "message": "Based on what you told me, this could be urgent. Please go to the emergency room now or call your local emergency number.",
        }

    if body.trend == "worse":
        return {
            "outcome": "URGENT",
            "message": "Thanks. Since it's getting worse, I recommend an urgent appointment within the next 24 to 48 hours.",
        }

    return {
        "outcome": "ROUTINE",
        "message": "Thanks. This sounds appropriate for a routine appointment. I can take your details for scheduling.",
    }


@router.post("/triage-decision")
async def triage_decision(request: Request):
    payload = await request.json()

    if "symptom" in payload and "duration" in payload:
        return _handle_triage(payload)

    tool_calls = extract_tool_calls(payload)
    results = []
    for tc in tool_calls:
        tool_call_id = tc.get("id") or tc.get("toolCallId")
        args = parse_args(tc)
        try:
            out = _handle_triage(args)
            results.append({
                "toolCallId": tool_call_id,
                "result": json.dumps(out, separators=(",", ":")),
            })
        except Exception as e:
            results.append({
                "toolCallId": tool_call_id,
                "result": f"Error: {e}",
            })

    return {"results": results}
