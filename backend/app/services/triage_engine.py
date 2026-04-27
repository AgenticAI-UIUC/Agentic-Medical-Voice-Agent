from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.config import settings
from app.services.rag_retriever import (
    RetrievedMedicalKnowledge,
    retrieve_medical_knowledge,
)
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
    (
        re.compile(
            r"chest\s+pain|chest\s+tight|chest\s+pressure|crushing\s+chest"
            r"|elephant(\s+is)?\s+(on|sitting\s+on)\s+(my\s+)?chest"
            r"|heavy\s+(weight|pressure)\s+(on|in)\s+(my\s+)?chest"
            r"|squeez\w*\s+(in\s+)?(my\s+)?chest"
            r"|heart\s+attack|cardiac\s+arrest",
            re.IGNORECASE,
        ),
        "cardiac emergency",
    ),
    # Stroke
    (
        re.compile(
            r"stroke|face\s+droop|slurred?\s+speech|sudden\s+(numb|weak)"
            r"|can\s*'?t\s+move\s+(arm|leg|side)",
            re.IGNORECASE,
        ),
        "possible stroke",
    ),
    # Breathing
    (
        re.compile(
            r"can\s*'?t\s+breathe|unable\s+to\s+breathe|not\s+breathing"
            r"|stopped?\s+breathing|choking|severe\s+(asthma|shortness\s+of\s+breath)",
            re.IGNORECASE,
        ),
        "respiratory emergency",
    ),
    # Bleeding / trauma
    (
        re.compile(
            r"uncontroll\w*\s+bleed|severe\s+bleed|won\s*'?t\s+stop\s+bleed"
            r"|massive\s+blood\s+loss|gunshot|stab\s+wound",
            re.IGNORECASE,
        ),
        "severe bleeding or trauma",
    ),
    # Consciousness
    (
        re.compile(
            r"unconscious|unresponsive|passed?\s+out\s+and\s+(not|won)"
            r"|seizure\s+won\s*'?t\s+stop|status\s+epilepticus",
            re.IGNORECASE,
        ),
        "loss of consciousness or prolonged seizure",
    ),
    # Anaphylaxis
    (
        re.compile(
            r"anaphyla\w*|throat\s+(closing|swell)|can\s*'?t\s+swallow\s+and\s+(can\s*'?t\s+breathe|swell)",
            re.IGNORECASE,
        ),
        "possible anaphylaxis",
    ),
    # Suicidal / self-harm
    (
        re.compile(
            r"want\s+to\s+(kill|end)\s+(myself|my\s+life|it\s+all)"
            r"|suicid|self.?harm|overdos",
            re.IGNORECASE,
        ),
        "mental health crisis",
    ),
    # Poisoning
    (
        re.compile(
            r"poison|swallowed\s+(bleach|chemical|battery)",
            re.IGNORECASE,
        ),
        "possible poisoning",
    ),
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


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return str(value).strip()
    return ""


def _coerce_symptom_inputs(symptoms: Any) -> list[str]:
    if symptoms is None:
        return []
    if isinstance(symptoms, (list, tuple, set)):
        items = list(symptoms)
    else:
        items = [symptoms]

    normalized: list[str] = []
    for item in items:
        text = _coerce_text(item)
        if text:
            normalized.append(text)
    return normalized


def classify_emergency(
    symptoms: list[str] | Any,
) -> tuple[bool, str | None, str | None]:
    """Check symptom text against red-flag patterns.

    Returns (is_emergency, matched_category, appropriate_message).
    """
    combined = " ".join(_coerce_symptom_inputs(symptoms)).strip()
    if not combined:
        return False, None, None

    for pattern, category in _RED_FLAG_PATTERNS:
        if pattern.search(combined):
            if category == "mental health crisis":
                return True, category, _MENTAL_HEALTH_EMERGENCY_MESSAGE
            return True, category, _EMERGENCY_MESSAGE

    return False, None, None


_AFFIRMATIVE_WORDS = frozenset(
    {
        "yes",
        "yeah",
        "yep",
        "correct",
        "right",
        "true",
        "definitely",
        "absolutely",
        "sure",
        "does",
        "did",
        "is",
        "it does",
        "always",
    }
)
_NEGATIVE_WORDS = frozenset(
    {
        "no",
        "nope",
        "not",
        "never",
        "none",
        "nah",
        "doesn't",
        "don't",
        "didn't",
        "haven't",
        "hasn't",
        "isn't",
        "rarely",
        "neither",
    }
)

# How much a single affirmative/negative answer shifts a specialty's score.
_ANSWER_BOOST = 1.5
_ANSWER_PENALTY = 0.6  # multiplicative – shrinks rather than removes
_SEMANTIC_SOURCE_QUESTION_LIMIT = 3
_ANSWER_KEYWORD_STOPWORDS = frozenset(
    {
        "about",
        "after",
        "also",
        "and",
        "any",
        "are",
        "both",
        "can",
        "did",
        "does",
        "for",
        "from",
        "had",
        "has",
        "have",
        "how",
        "is",
        "it",
        "its",
        "long",
        "more",
        "or",
        "the",
        "their",
        "them",
        "they",
        "this",
        "you",
        "your",
    }
)

_SYMPTOM_ALIASES: dict[str, list[str]] = {
    "migraine": ["headache"],
    "migraines": ["migraine", "headache"],
    "headaches": ["headache"],
    "nauseous": ["nausea"],
}


def _normalize_symptom_text(symptom: Any) -> str:
    text = _coerce_text(symptom).lower()
    normalized = re.sub(r"[^a-z0-9\s]", " ", text)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _singularize_symptom(symptom: str) -> str:
    if symptom.endswith("ies") and len(symptom) > 3:
        return f"{symptom[:-3]}y"
    if symptom.endswith("s") and not symptom.endswith("ss") and len(symptom) > 3:
        return symptom[:-1]
    return symptom


def _symptom_query_terms(symptom: Any) -> list[str]:
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


def _classify_answer(answer: Any) -> float:
    """Return +1 for affirmative, -1 for negative, 0 for neutral."""
    text = _coerce_text(answer).lower()
    if not text:
        return 0.0

    words = set(text.split())
    affirm = len(words & _AFFIRMATIVE_WORDS)
    negate = len(words & _NEGATIVE_WORDS)
    if affirm > negate:
        return 1.0
    if negate > affirm:
        return -1.0
    return 0.0


def _answer_keywords(text: Any) -> set[str]:
    normalized = _normalize_symptom_text(text)
    if not normalized:
        return set()
    return {
        token
        for token in normalized.split()
        if len(token) > 2 and token not in _ANSWER_KEYWORD_STOPWORDS
    }


def _classify_answer_for_question(question: Any, answer: Any) -> float:
    classification = _classify_answer(answer)
    if classification != 0.0:
        return classification

    # Follow-up answers are often not yes/no in voice calls. If the patient
    # answers with terms from the question ("vision changes", "start suddenly"),
    # treat that as confirming the specialty-specific follow-up.
    if _answer_keywords(question) & _answer_keywords(answer):
        return 1.0

    return 0.0


def _apply_answer_adjustments(
    scores: dict[str, float],
    question_to_specialties: dict[str, list[str]],
    answers: dict[str, Any],
) -> None:
    """Adjust specialty scores in-place based on follow-up answers."""
    for question, response in answers.items():
        question_text = _coerce_text(question)
        if not question_text:
            continue
        classification = _classify_answer_for_question(question_text, response)
        if classification == 0.0:
            continue
        specialty_ids = question_to_specialties.get(question_text, [])
        for sid in specialty_ids:
            if sid not in scores:
                continue
            if classification > 0:
                scores[sid] = scores[sid] + _ANSWER_BOOST
            else:
                scores[sid] = scores[sid] * _ANSWER_PENALTY


def _semantic_search_enabled(explicit: bool | None = None) -> bool:
    if explicit is not None:
        return explicit
    return settings.TRIAGE_SEMANTIC_SEARCH_ENABLED


def _build_semantic_query(symptom_texts: list[str], description: str | None) -> str:
    description_text = _coerce_text(description)
    if description_text:
        return description_text
    return ". ".join(symptom_texts)


def _add_unique_questions(
    questions: dict[str, list[str]],
    specialty_id: str,
    new_questions: Any,
) -> None:
    if not isinstance(new_questions, list):
        return

    existing = questions.setdefault(specialty_id, [])
    for question in new_questions[:_SEMANTIC_SOURCE_QUESTION_LIMIT]:
        question_text = _coerce_text(question)
        if question_text and question_text not in existing:
            existing.append(question_text)


def _apply_semantic_matches(
    scores: dict[str, float],
    names: dict[str, str],
    questions: dict[str, list[str]],
    chunks: list[RetrievedMedicalKnowledge],
) -> None:
    """Fold vector-search matches into the same specialty score map."""
    for chunk in chunks:
        metadata = chunk.get("metadata", {})
        specialty_id = _coerce_text(metadata.get("specialty_id"))
        if not specialty_id:
            continue

        similarity = float(chunk.get("similarity") or 0.0)
        if similarity <= 0.0:
            continue

        semantic_score = similarity * settings.TRIAGE_SEMANTIC_SCORE_SCALE
        scores[specialty_id] = scores.get(specialty_id, 0.0) + semantic_score

        specialty_name = _coerce_text(metadata.get("specialty_name"))
        if specialty_name and specialty_id not in names:
            names[specialty_id] = specialty_name

        _add_unique_questions(
            questions,
            specialty_id,
            metadata.get("follow_up_questions"),
        )


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
    symptoms: Any,
    answers: dict[str, Any] | None = None,
    confidence_threshold: float = 0.6,
    description: str | None = None,
    semantic_search_enabled: bool | None = None,
) -> TriageResult:
    """
    Score specialties from keyword matches and optional semantic retrieval.

    Args:
        symptoms: List of symptom strings from the patient.
        answers: Previous follow-up answers keyed by question text.
            Affirmative answers boost the linked specialty; negative answers penalize it.
        confidence_threshold: Minimum confidence to consider specialty determined.
        description: Full natural-language symptom description, if available.
        semantic_search_enabled: Override the TRIAGE_SEMANTIC_SEARCH_ENABLED setting.
    """
    symptom_texts = _coerce_symptom_inputs(symptoms)
    answers = answers if isinstance(answers, dict) else {}
    if not symptom_texts:
        return TriageResult(
            specialty_determined=False,
            follow_up_questions=["Could you describe your symptoms?"],
        )

    # --- Emergency guard: runs BEFORE any specialty matching ---
    emergency_inputs = [*symptom_texts, _coerce_text(description)]
    is_emergency, category, emsg = classify_emergency(emergency_inputs)
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
    for symptom in symptom_texts:
        for term in _symptom_query_terms(symptom):
            res = (
                sb.table("symptom_specialty_map")
                .select(
                    "symptom,specialty_id,weight,follow_up_questions,specialties(id,name)"
                )
                .ilike("symptom", f"%{term}%")
                .execute()
            )
            rows = getattr(res, "data", None) or []
            for row in rows:
                row_key = (
                    str(row.get("symptom") or ""),
                    str(row.get("specialty_id") or ""),
                )
                if row_key in seen_rows:
                    continue
                seen_rows.add(row_key)
                all_rows.append(row)

    # Score specialties by summing keyword weights.
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

    # Optional semantic path: embed the patient's natural wording and add
    # vector-similar knowledge chunks into the same score map.
    if _semantic_search_enabled(semantic_search_enabled):
        semantic_query = _build_semantic_query(symptom_texts, description)
        try:
            chunks = retrieve_medical_knowledge(
                semantic_query,
                match_count=settings.TRIAGE_SEMANTIC_MATCH_COUNT,
                match_threshold=settings.TRIAGE_SEMANTIC_MATCH_THRESHOLD,
            )
            _apply_semantic_matches(scores, names, questions, chunks)
        except Exception:
            # Semantic search is additive. Missing OpenAI config, network failures,
            # or an unapplied pgvector migration should not break keyword triage.
            pass

    if not scores:
        return TriageResult(
            specialty_determined=False,
            follow_up_questions=[
                "I wasn't able to match those symptoms. "
                "Could you describe them in more detail?"
            ],
        )

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
        {
            "specialty_id": sid,
            "specialty_name": names.get(sid, ""),
            "score": round(sc / total, 2),
        }
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
    already_asked = (
        {_coerce_text(question) for question in answers.keys()} if answers else set()
    )
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
