#!/usr/bin/env bash

set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root/backend"

if [[ -x ".venv/bin/python" ]]; then
  python_bin=".venv/bin/python"
elif command -v uv >/dev/null 2>&1; then
  python_bin="uv run python"
else
  echo "Unable to run semantic triage test." >&2
  echo "Set up the backend environment first with 'cd backend && uv sync'." >&2
  exit 1
fi

$python_bin - <<'PY'
from __future__ import annotations

import json
import sys
from dataclasses import asdict

from app.config import settings
from app.services.triage_engine import triage_symptoms


def dump(label: str, result) -> None:
    print(f"\n=== {label} ===")
    print(json.dumps(asdict(result), indent=2, sort_keys=True))


def fail(message: str) -> None:
    print(f"\nFAIL: {message}", file=sys.stderr)
    sys.exit(1)


if not settings.TRIAGE_SEMANTIC_SEARCH_ENABLED:
    fail("TRIAGE_SEMANTIC_SEARCH_ENABLED is false. Enable it before running this test.")

if not settings.OPENAI_API_KEY.strip():
    fail("OPENAI_API_KEY is not configured. Semantic retrieval needs embeddings.")


description = (
    "I keep getting this sharp pain behind my eyes, and sometimes I see "
    "flashing zigzag lights before it starts."
)
symptoms = ["sharp pain behind my eyes", "flashing zigzag lights"]

initial = triage_symptoms(symptoms, description=description)
dump("Initial Semantic Triage", initial)

answers = {
    "Do you have vision changes, light sensitivity, numbness, or tingling?": "vision changes",
    "Did the symptoms start suddenly or have they been recurring?": "start suddenly",
}
after_followups = triage_symptoms(
    symptoms,
    answers=answers,
    description=description,
)
dump("After Follow-Up Answers", after_followups)

if not after_followups.specialty_determined:
    fail("Expected semantic triage to determine a specialty after follow-up answers.")

if after_followups.specialty_name != "Neurology":
    fail(f"Expected Neurology, got {after_followups.specialty_name!r}.")

emergency = triage_symptoms(
    ["chest discomfort"],
    description="It feels like an elephant is sitting on my chest.",
)
dump("Emergency Guard Check", emergency)

if not emergency.is_emergency:
    fail("Expected elephant-on-chest wording to trigger the emergency guard.")

print("\nPASS: semantic triage demo path resolves to Neurology and emergency guard works.")
PY
