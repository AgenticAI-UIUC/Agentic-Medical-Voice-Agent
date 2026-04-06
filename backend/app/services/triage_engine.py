from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.supabase import get_supabase

# ---------------------------------------------------------------------------
# Emergency / red-flag detection
# ---------------------------------------------------------------------------
# Each entry is a compiled regex that fires on the *combined* symptom text.
# Patterns are intentionally broad — false positives are acceptable here
# because the cost of missing a true emergency far outweighs asking someone
# to call 911 unnecessarily.
_RED_FLAG_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Cardiac
    (re.compile(
        r"chest\s+pain|chest\s+tight|chest\s+pressure|crushing\s+chest"
        r"|heart\s+attack|cardiac\s+arrest",
        re.IGNORECASE,
    ), "cardiac emergency"),
    # Stroke
    (re.compile(
        r"stroke|face\s+droop|slurred?\s+speech|sudden\s+(numb|weak)"
        r"|can\s*'?t\s+move\s+(arm|leg|side)",
        re.IGNORECASE,
    ), "possible stroke"),
    # Breathing
    (re.compile(
        r"can\s*'?t\s+breathe|unable\s+to\s+breathe|not\s+breathing"
        r"|stopped?\s+breathing|choking|severe\s+(asthma|shortness\s+of\s+breath)",
        re.IGNORECASE,
    ), "respiratory emergency"),
    # Bleeding / trauma
    (re.compile(
        r"uncontroll\w*\s+bleed|severe\s+bleed|won\s*'?t\s+stop\s+bleed"
        r"|massive\s+blood\s+loss|gunshot|stab\s+wound",
        re.IGNORECASE,
    ), "severe bleeding or trauma"),
    # Consciousness
    (re.compile(
        r"unconscious|unresponsive|passed?\s+out\s+and\s+(not|won)"
        r"|seizure\s+won\s*'?t\s+stop|status\s+epilepticus",
        re.IGNORECASE,
    ), "loss of consciousness or prolonged seizure"),
    # Anaphylaxis
    (re.compile(
        r"anaphyla\w*|throat\s+(closing|swell)|can\s*'?t\s+swallow\s+and\s+(can\s*'?t\s+breathe|swell)",
        re.IGNORECASE,
    ), "possible anaphylaxis"),
    # Suicidal / self-harm
    (re.compile(
        r"want\s+to\s+(kill|end)\s+(myself|my\s+life|it\s+all)"
        r"|suicid|self.?harm|overdos",
        re.IGNORECASE,
    ), "mental health crisis"),
    # Poisoning
    (re.compile(
        r"poison|swallowed\s+(bleach|chemical|battery)",
        re.IGNORECASE,
    ), "possible poisoning"),
]

_EMERGENCY_MESSAGE = (
    "Based on what you're describing, this sounds like it could be a medical emergency. "
    "Please call 911 or go to your nearest emergency room immediately. "
    "Do not wait to schedule an appointment."
)

_MENTAL_HEALTH_EMERGENCY_MESSAGE = (
    "It sounds like you may be in crisis. Please call 988 (Suicide & Crisis Lifeline) "
    "or 911 right away. You can also text HOME to 741741 to reach the Crisis Text Line. "
    "You are not alone, and help is available now."
)


def classify_emergency(symptoms: list[str]) -> tuple[bool, str | None, str | None]:
    """Check symptom text against red-flag patterns.

    Returns (is_emergency, matched_category, appropriate_message).
    """
    combined = " ".join(symptoms).strip()
    if not combined:
        return False, None, None

    for pattern, category in _RED_FLAG_PATTERNS:
        if pattern.search(combined):
            if category == "mental health crisis":
                return True, category, _MENTAL_HEALTH_EMERGENCY_MESSAGE
            return True, category, _EMERGENCY_MESSAGE

    return False, None, None


_AFFIRMATIVE_WORDS = frozenset({
    "yes", "yeah", "yep", "correct", "right", "true", "definitely",
    "absolutely", "sure", "does", "did", "is", "it does", "always",
})
_NEGATIVE_WORDS = frozenset({
    "no", "nope", "not", "never", "none", "nah", "doesn't", "don't",
    "didn't", "haven't", "hasn't", "isn't", "rarely", "neither",
})

# How much a single affirmative/negative answer shifts a specialty's score.
_ANSWER_BOOST = 1.5
_ANSWER_PENALTY = 0.6  # multiplicative – shrinks rather than removes

_SYMPTOM_ALIASES: dict[str, list[str]] = {
    "migraine": ["headache"],
    "migraines": ["migraine", "headache"],
    "headaches": ["headache"],
    "nauseous": ["nausea"],
}


def _normalize_symptom_text(symptom: str) -> str:
    normalized = re.sub(r"[^a-z0-9\s]", " ", symptom.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _singularize_symptom(symptom: str) -> str:
    if symptom.endswith("ies") and len(symptom) > 3:
        return f"{symptom[:-3]}y"
    if symptom.endswith("s") and not symptom.endswith("ss") and len(symptom) > 3:
        return symptom[:-1]
    return symptom


def _symptom_query_terms(symptom: str) -> list[str]:
    base = _normalize_symptom_text(symptom)
    if not base:
        return []

    terms: list[str] = [base]
    singular = _singularize_symptom(base)
    if singular != base:
        terms.append(singular)

    for term in list(terms):
        terms.extend(_SYMPTOM_ALIASES.get(term, []))

    seen: set[str] = set()
    ordered_terms: list[str] = []
    for term in terms:
        if term and term not in seen:
            seen.add(term)
            ordered_terms.append(term)
    return ordered_terms


def _classify_answer(answer: str) -> float:
    """Return +1 for affirmative, -1 for negative, 0 for neutral."""
    words = set(answer.lower().split())
    affirm = len(words & _AFFIRMATIVE_WORDS)
    negate = len(words & _NEGATIVE_WORDS)
    if affirm > negate:
        return 1.0
    if negate > affirm:
        return -1.0
    return 0.0


def _apply_answer_adjustments(
    scores: dict[str, float],
    question_to_specialties: dict[str, list[str]],
    answers: dict[str, str],
) -> None:
    """Adjust specialty scores in-place based on follow-up answers."""
    for question, response in answers.items():
        classification = _classify_answer(response)
        if classification == 0.0:
            continue
        specialty_ids = question_to_specialties.get(question, [])
        for sid in specialty_ids:
            if sid not in scores:
                continue
            if classification > 0:
                scores[sid] = scores[sid] + _ANSWER_BOOST
            else:
                scores[sid] = scores[sid] * _ANSWER_PENALTY


@dataclass
class TriageResult:
    specialty_determined: bool
    specialty_id: str | None = None
    specialty_name: str | None = None
    confidence: float = 0.0
    follow_up_questions: list[str] = field(default_factory=list)
    top_candidates: list[dict[str, Any]] = field(default_factory=list)
    is_emergency: bool = False
    emergency_category: str | None = None
    emergency_message: str | None = None


def triage_symptoms(
    symptoms: list[str],
    answers: dict[str, str] | None = None,
    confidence_threshold: float = 0.6,
) -> TriageResult:
    """
    Given a list of symptom keywords, query symptom_specialty_map and
    score specialties. If confidence is above threshold, return the
    specialty. Otherwise return follow-up questions to narrow it down.

    Args:
        symptoms: List of symptom strings from the patient.
        answers: Previous follow-up answers keyed by question text.
            Affirmative answers boost the linked specialty; negative answers penalize it.
        confidence_threshold: Minimum confidence to consider specialty determined.
    """
    if not symptoms:
        return TriageResult(
            specialty_determined=False,
            follow_up_questions=["Could you describe your symptoms?"],
        )

    # --- Emergency guard: runs BEFORE any specialty matching ---
    is_emergency, category, emsg = classify_emergency(symptoms)
    if is_emergency:
        return TriageResult(
            specialty_determined=False,
            is_emergency=True,
            emergency_category=category,
            emergency_message=emsg,
        )

    sb = get_supabase()

    # Query all matching symptom rows
    # Use ilike for case-insensitive partial matching
    all_rows: list[dict[str, Any]] = []
    seen_rows: set[tuple[str, str]] = set()
    for symptom in symptoms:
        for term in _symptom_query_terms(symptom):
            res = (
                sb.table("symptom_specialty_map")
                .select("symptom,specialty_id,weight,follow_up_questions,specialties(id,name)")
                .ilike("symptom", f"%{term}%")
                .execute()
            )
            rows = getattr(res, "data", None) or []
            for row in rows:
                row_key = (str(row.get("symptom") or ""), str(row.get("specialty_id") or ""))
                if row_key in seen_rows:
                    continue
                seen_rows.add(row_key)
                all_rows.append(row)

    if not all_rows:
        return TriageResult(
            specialty_determined=False,
            follow_up_questions=[
                "I wasn't able to match those symptoms. "
                "Could you describe them in more detail?"
            ],
        )

    # Score specialties by summing weights
    scores: dict[str, float] = {}
    names: dict[str, str] = {}
    questions: dict[str, list[str]] = {}

    for row in all_rows:
        sid = row["specialty_id"]
        w = float(row.get("weight") or 1.0)
        scores[sid] = scores.get(sid, 0.0) + w

        spec = row.get("specialties")
        if spec and isinstance(spec, dict):
            names[sid] = spec.get("name", "")

        fq = row.get("follow_up_questions")
        if fq and isinstance(fq, list):
            questions.setdefault(sid, []).extend(fq)

    # Apply follow-up answer adjustments before normalizing
    if answers:
        # Build reverse map: question text → list of specialty IDs
        question_to_specialties: dict[str, list[str]] = {}
        for sid, q_list in questions.items():
            for q in q_list:
                question_to_specialties.setdefault(q, []).append(sid)
        _apply_answer_adjustments(scores, question_to_specialties, answers)
        # Clamp scores so they don't go negative
        for sid in scores:
            if scores[sid] < 0.0:
                scores[sid] = 0.0

    # Normalize scores
    total = sum(scores.values()) or 1.0
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    top_id, top_score = ranked[0]
    confidence = top_score / total

    top_candidates = [
        {"specialty_id": sid, "specialty_name": names.get(sid, ""), "score": round(sc / total, 2)}
        for sid, sc in ranked[:3]
    ]

    if confidence >= confidence_threshold:
        return TriageResult(
            specialty_determined=True,
            specialty_id=top_id,
            specialty_name=names.get(top_id, ""),
            confidence=round(confidence, 2),
            top_candidates=top_candidates,
        )

    # Not confident — gather follow-up questions from top candidates,
    # excluding questions that were already answered.
    already_asked = set(answers.keys()) if answers else set()
    follow_ups: list[str] = []
    for sid, _ in ranked[:2]:
        for q in questions.get(sid, []):
            if q not in already_asked:
                follow_ups.append(q)

    if not follow_ups:
        follow_ups = [
            "Can you tell me more about when these symptoms started?",
            "Are your symptoms getting worse, staying the same, or improving?",
        ]

    return TriageResult(
        specialty_determined=False,
        confidence=round(confidence, 2),
        follow_up_questions=follow_ups[:3],
        top_candidates=top_candidates,
    )


def get_all_specialties() -> list[dict[str, str]]:
    """Return all specialties for fallback selection."""
    sb = get_supabase()
    res = sb.table("specialties").select("id,name,description").order("name").execute()
    return getattr(res, "data", None) or []
