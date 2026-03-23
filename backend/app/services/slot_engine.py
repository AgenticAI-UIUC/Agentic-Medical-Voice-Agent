from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.config import settings
from app.services.time_utils import (
    DayRange,
    day_range_to_utc,
    is_in_bucket,
    now_utc,
    parse_preferred_day,
    parse_time_bucket,
    format_for_voice,
    Bucket,
)
from app.supabase import get_supabase


NEXT_AVAILABLE_ALIASES = {
    "next available day", "next available date", "next available",
    "soonest", "earliest", "earliest available",
}


def _fetch_availability(doctor_id: str) -> list[dict[str, Any]]:
    """Fetch weekly availability rows for a doctor."""
    sb = get_supabase()
    res = (
        sb.table("doctor_availability")
        .select("day_of_week,start_time,end_time,slot_minutes,timezone")
        .eq("doctor_id", doctor_id)
        .execute()
    )
    return getattr(res, "data", None) or []


def _fetch_booked(doctor_id: str, start_utc: datetime, end_utc: datetime) -> set[datetime]:
    """Return set of start_at datetimes that are already booked (non-cancelled)."""
    sb = get_supabase()
    res = (
        sb.table("appointments")
        .select("start_at")
        .eq("doctor_id", doctor_id)
        .neq("status", "CANCELLED")
        .gte("start_at", start_utc.isoformat())
        .lt("start_at", end_utc.isoformat())
        .execute()
    )
    rows = getattr(res, "data", None) or []
    booked = set()
    for r in rows:
        s = r["start_at"].replace("Z", "+00:00")
        booked.add(datetime.fromisoformat(s))
    return booked


def _fetch_blocks(doctor_id: str, start_utc: datetime, end_utc: datetime) -> list[tuple[datetime, datetime]]:
    """Return list of (block_start, block_end) in UTC."""
    sb = get_supabase()
    res = (
        sb.table("doctor_blocks")
        .select("start_at,end_at")
        .eq("doctor_id", doctor_id)
        .lt("start_at", end_utc.isoformat())
        .gt("end_at", start_utc.isoformat())
        .execute()
    )
    rows = getattr(res, "data", None) or []
    blocks = []
    for r in rows:
        bs = datetime.fromisoformat(r["start_at"].replace("Z", "+00:00"))
        be = datetime.fromisoformat(r["end_at"].replace("Z", "+00:00"))
        blocks.append((bs, be))
    return blocks


def _is_blocked(slot_start: datetime, slot_end: datetime, blocks: list[tuple[datetime, datetime]]) -> bool:
    """Check if a slot overlaps any block."""
    for bs, be in blocks:
        if slot_start < be and slot_end > bs:
            return True
    return False


def _generate_theoretical_slots(
    availability: list[dict[str, Any]],
    start_date_utc: datetime,
    end_date_utc: datetime,
) -> list[tuple[datetime, datetime]]:
    """Generate all theoretical slot (start, end) pairs from availability templates."""
    slots: list[tuple[datetime, datetime]] = []

    # Group availability by day_of_week
    by_dow: dict[int, list[dict[str, Any]]] = {}
    for row in availability:
        dow = row["day_of_week"]
        by_dow.setdefault(dow, []).append(row)

    current = start_date_utc.date() if hasattr(start_date_utc, "date") else start_date_utc
    end_d = end_date_utc.date() if hasattr(end_date_utc, "date") else end_date_utc

    # Iterate day by day
    d = start_date_utc.astimezone(timezone.utc).date() if isinstance(start_date_utc, datetime) else start_date_utc
    end_d = end_date_utc.astimezone(timezone.utc).date() if isinstance(end_date_utc, datetime) else end_date_utc

    day = d
    while day < end_d:
        # Python weekday: Mon=0..Sun=6 → Schema: Sun=0..Sat=6
        schema_dow = (day.weekday() + 1) % 7
        windows = by_dow.get(schema_dow, [])

        for window in windows:
            tz = ZoneInfo(window.get("timezone") or settings.CLINIC_TIMEZONE)
            slot_minutes = int(window.get("slot_minutes") or 60)
            slot_len = timedelta(minutes=slot_minutes)

            # Parse start/end times
            st = window["start_time"]
            et = window["end_time"]
            if isinstance(st, str):
                parts = st.split(":")
                st = time(int(parts[0]), int(parts[1]))
            if isinstance(et, str):
                parts = et.split(":")
                et = time(int(parts[0]), int(parts[1]))

            window_start = datetime.combine(day, st, tzinfo=tz).astimezone(timezone.utc)
            window_end = datetime.combine(day, et, tzinfo=tz).astimezone(timezone.utc)

            cur = window_start
            while cur + slot_len <= window_end:
                slots.append((cur, cur + slot_len))
                cur += slot_len

        day += timedelta(days=1)

    return slots


def _find_slots_in_window(
    doctor_id: str,
    w_start: datetime,
    w_end: datetime,
    bucket: Bucket,
    max_slots: int,
) -> list[dict[str, Any]]:
    """Low-level: find available slots for a doctor within an explicit UTC window."""
    now = now_utc()
    if w_end <= now:
        return []
    if w_start < now:
        w_start = now

    availability = _fetch_availability(doctor_id)
    if not availability:
        return []

    booked = _fetch_booked(doctor_id, w_start, w_end)
    blocks = _fetch_blocks(doctor_id, w_start, w_end)
    theoretical = _generate_theoretical_slots(availability, w_start, w_end)

    available = []
    for start, end in theoretical:
        if start < now:
            continue
        if start in booked:
            continue
        if _is_blocked(start, end, blocks):
            continue
        if not is_in_bucket(start, bucket):
            continue
        available.append({
            "start_at": start.isoformat(),
            "end_at": end.isoformat(),
            "label": format_for_voice(start),
        })
        if len(available) >= max_slots:
            break

    return available


def _find_specialty_slots_in_window(
    specialty_id: str,
    w_start: datetime,
    w_end: datetime,
    bucket: Bucket,
    max_slots: int,
) -> list[dict[str, Any]]:
    """Find slots across all active doctors with a given specialty within an explicit UTC window."""
    sb = get_supabase()
    res = (
        sb.table("doctor_specialties")
        .select("doctor_id,doctors(id,full_name,is_active)")
        .eq("specialty_id", specialty_id)
        .execute()
    )
    rows = getattr(res, "data", None) or []

    all_slots: list[dict[str, Any]] = []
    for row in rows:
        doctor = row.get("doctors")
        if not doctor or not doctor.get("is_active"):
            continue
        doc_id = doctor["id"]
        doc_name = doctor["full_name"]

        slots = _find_slots_in_window(doc_id, w_start, w_end, bucket, max_slots=max_slots)
        for s in slots:
            s["doctor_id"] = doc_id
            s["doctor_name"] = doc_name
        all_slots.extend(slots)

    all_slots.sort(key=lambda s: s["start_at"])
    return all_slots[:max_slots]


def _parse_window(preferred_day: str) -> tuple[datetime, datetime, bool]:
    """
    Parse preferred_day into a UTC (w_start, w_end) and a flag indicating
    whether it was an open-ended "next available" request.
    """
    now = now_utc()
    horizon = now + timedelta(days=settings.SCHEDULING_HORIZON_DAYS)
    day_raw = (preferred_day or "").strip().lower()

    if day_raw in NEXT_AVAILABLE_ALIASES:
        return now, horizon, True

    dr = parse_preferred_day(preferred_day)
    w_start, w_end = day_range_to_utc(dr)
    if w_end > horizon:
        w_end = horizon
    return w_start, w_end, False


def find_available_slots(
    doctor_id: str,
    preferred_day: str,
    preferred_time: str,
    max_slots: int = 5,
) -> list[dict[str, Any]]:
    """
    Compute available slots for a doctor given day/time preferences.
    Returns a list of {start_at, end_at, label} dicts.
    """
    bucket = parse_time_bucket(preferred_time)
    w_start, w_end, _ = _parse_window(preferred_day)
    return _find_slots_in_window(doctor_id, w_start, w_end, bucket, max_slots)


def find_slots_for_specialty(
    specialty_id: str,
    preferred_day: str,
    preferred_time: str,
    max_slots: int = 5,
) -> list[dict[str, Any]]:
    """
    Find available slots across all active doctors with a given specialty.
    Returns slots with doctor info attached.
    """
    bucket = parse_time_bucket(preferred_time)
    w_start, w_end, _ = _parse_window(preferred_day)
    return _find_specialty_slots_in_window(specialty_id, w_start, w_end, bucket, max_slots)


def find_slots_with_extension(
    *,
    specialty_id: str | None = None,
    doctor_id: str | None = None,
    preferred_day: str,
    preferred_time: str,
    max_slots: int = 5,
) -> dict[str, Any]:
    """
    Find slots, extending the search window by ±1× the requested duration if
    nothing is found in the originally requested range.

    Returns {"slots": [...], "window_note": str | None}.
    window_note is non-None when results come from an extended window and
    contains a human-readable explanation for the voice agent to relay.
    """
    now = now_utc()
    horizon = now + timedelta(days=settings.SCHEDULING_HORIZON_DAYS)
    bucket = parse_time_bucket(preferred_time)
    w_start, w_end, is_open_ended = _parse_window(preferred_day)

    def _get_slots(ws: datetime, we: datetime) -> list[dict[str, Any]]:
        if specialty_id:
            return _find_specialty_slots_in_window(specialty_id, ws, we, bucket, max_slots)
        if doctor_id:
            slots = _find_slots_in_window(doctor_id, ws, we, bucket, max_slots)
            for s in slots:
                s["doctor_id"] = doctor_id
            return slots
        return []

    # Try original window first
    slots = _get_slots(w_start, w_end)
    if slots or is_open_ended:
        return {"slots": slots, "window_note": None}

    # No slots found — extend by ±1× the window duration, clamped to [now, horizon]
    window_duration = w_end - w_start

    fwd_start = w_end
    fwd_end = min(w_end + window_duration, horizon)
    bwd_end = w_start
    bwd_start = max(now, w_start - window_duration)

    forward_slots = _get_slots(fwd_start, fwd_end) if fwd_end > fwd_start else []
    backward_slots = _get_slots(bwd_start, bwd_end) if bwd_end > bwd_start else []

    extended = sorted(backward_slots + forward_slots, key=lambda s: s["start_at"])[:max_slots]
    if not extended:
        return {"slots": [], "window_note": None}

    return {
        "slots": extended,
        "window_note": (
            "No times were available in your requested window. "
            "Here are the closest available times I found"
        ),
    }
