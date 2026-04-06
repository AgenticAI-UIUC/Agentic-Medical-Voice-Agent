from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
import re
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
    "as soon as possible", "asap", "soonest available",
}


def _normalize_preference_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (value or "").strip().lower())).strip()


def is_next_available_request(preferred_day: str) -> bool:
    normalized = _normalize_preference_text(preferred_day)
    return any(alias in normalized for alias in NEXT_AVAILABLE_ALIASES)


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


def validate_slot(
    doctor_id: str,
    start_dt: datetime,
    end_dt: datetime,
) -> str | None:
    """
    Validate that a requested slot is bookable. Returns None if valid,
    or an error message string if invalid.
    """
    now = now_utc()
    horizon = now + timedelta(days=settings.SCHEDULING_HORIZON_DAYS)

    # 1. Slot must be in the future and within the scheduling horizon
    if start_dt < now:
        return "That time has already passed. Please choose a future time."
    if start_dt > horizon:
        return (
            f"We can only book up to {settings.SCHEDULING_HORIZON_DAYS} days out. "
            "Please choose an earlier date."
        )

    # 2. Doctor must be active
    sb = get_supabase()
    doc_res = (
        sb.table("doctors")
        .select("id,is_active")
        .eq("id", doctor_id)
        .limit(1)
        .execute()
    )
    doc_rows = getattr(doc_res, "data", None) or []
    if not doc_rows:
        return "That doctor was not found in our system."
    if not doc_rows[0].get("is_active"):
        return "That doctor is not currently accepting appointments."

    # 3. Slot must match an availability template (day, time window, duration)
    availability = _fetch_availability(doctor_id)
    if not availability:
        return "That doctor has no availability configured."

    slot_duration = end_dt - start_dt
    matched = False
    for window in availability:
        tz = ZoneInfo(window.get("timezone") or settings.CLINIC_TIMEZONE)
        slot_minutes = int(window.get("slot_minutes") or 60)

        if slot_duration != timedelta(minutes=slot_minutes):
            continue

        # Convert requested slot to the doctor's local timezone for day/time check
        local_start = start_dt.astimezone(tz)
        local_end = end_dt.astimezone(tz)

        # Check day of week (schema: Sun=0..Sat=6)
        schema_dow = (local_start.weekday() + 1) % 7
        if window["day_of_week"] != schema_dow:
            continue

        # Parse window start/end times
        st = window["start_time"]
        et = window["end_time"]
        if isinstance(st, str):
            parts = st.split(":")
            st = time(int(parts[0]), int(parts[1]))
        if isinstance(et, str):
            parts = et.split(":")
            et = time(int(parts[0]), int(parts[1]))

        if local_start.time() >= st and local_end.time() <= et:
            matched = True
            break

    if not matched:
        return "That time is outside the doctor's available hours."

    # 4. Slot must not be blocked
    blocks = _fetch_blocks(doctor_id, start_dt, end_dt)
    if _is_blocked(start_dt, end_dt, blocks):
        return "The doctor is unavailable during that time."

    # 5. Slot must not overlap any existing booking
    sb2 = get_supabase()
    overlap_res = (
        sb2.table("appointments")
        .select("id")
        .eq("doctor_id", doctor_id)
        .eq("status", "CONFIRMED")
        .lt("start_at", end_dt.isoformat())
        .gt("end_at", start_dt.isoformat())
        .limit(1)
        .execute()
    )
    if getattr(overlap_res, "data", None):
        return "That slot is already booked."

    return None


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
    now = now_utc()
    horizon = now + timedelta(days=settings.SCHEDULING_HORIZON_DAYS)

    bucket = parse_time_bucket(preferred_time)

    # Determine UTC search window
    if is_next_available_request(preferred_day):
        w_start, w_end = now, horizon
    else:
        dr = parse_preferred_day(preferred_day)
        w_start, w_end = day_range_to_utc(dr)

    # Clamp to [now, horizon]
    if w_end <= now:
        return []
    if w_start < now:
        w_start = now
    if w_end > horizon:
        w_end = horizon

    availability = _fetch_availability(doctor_id)
    if not availability:
        return []

    booked = _fetch_booked(doctor_id, w_start, w_end)
    blocks = _fetch_blocks(doctor_id, w_start, w_end)

    theoretical = _generate_theoretical_slots(availability, w_start, w_end)

    # Filter: not in past, not booked, not blocked, matches bucket
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
    sb = get_supabase()

    # Get active doctors with this specialty
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
        doctor_id = doctor["id"]
        doctor_name = doctor["full_name"]

        slots = find_available_slots(doctor_id, preferred_day, preferred_time, max_slots=max_slots)
        for s in slots:
            s["doctor_id"] = doctor_id
            s["doctor_name"] = doctor_name
        all_slots.extend(slots)

    # Sort by start time, take top N
    all_slots.sort(key=lambda s: s["start_at"])
    return all_slots[:max_slots]
