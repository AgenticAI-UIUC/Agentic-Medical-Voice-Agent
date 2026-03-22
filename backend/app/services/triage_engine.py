from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.supabase import get_supabase


@dataclass
class TriageResult:
    specialty_determined: bool
    specialty_id: str | None = None
    specialty_name: str | None = None
    confidence: float = 0.0
    follow_up_questions: list[str] = field(default_factory=list)
    top_candidates: list[dict[str, Any]] = field(default_factory=list)


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
        answers: Previous follow-up answers (for context, not yet used in scoring).
        confidence_threshold: Minimum confidence to consider specialty determined.
    """
    if not symptoms:
        return TriageResult(
            specialty_determined=False,
            follow_up_questions=["Could you describe your symptoms?"],
        )

    sb = get_supabase()

    # Query all matching symptom rows
    # Use ilike for case-insensitive partial matching
    all_rows: list[dict[str, Any]] = []
    for symptom in symptoms:
        res = (
            sb.table("symptom_specialty_map")
            .select("symptom,specialty_id,weight,follow_up_questions,specialties(id,name)")
            .ilike("symptom", f"%{symptom.strip()}%")
            .execute()
        )
        rows = getattr(res, "data", None) or []
        all_rows.extend(rows)

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

    # Not confident — gather follow-up questions from top candidates
    follow_ups: list[str] = []
    for sid, _ in ranked[:2]:
        follow_ups.extend(questions.get(sid, []))

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
