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


def _fetch_booked(doctor_id: str, start_utc: datetime, end_utc: datetime) -> list[tuple[datetime, datetime]]:
    """Return list of (start, end) for active (non-cancelled) appointments that
    overlap the given window. Uses full range overlap check, not just start_at."""
    sb = get_supabase()
    res = (
        sb.table("appointments")
        .select("start_at,end_at")
        .eq("doctor_id", doctor_id)
        .neq("status", "CANCELLED")
        .lt("start_at", end_utc.isoformat())
        .gt("end_at", start_utc.isoformat())
        .execute()
    )
    rows = getattr(res, "data", None) or []
    booked: list[tuple[datetime, datetime]] = []
    for r in rows:
        bs = datetime.fromisoformat(r["start_at"].replace("Z", "+00:00"))
        be = datetime.fromisoformat(r["end_at"].replace("Z", "+00:00"))
        booked.append((bs, be))
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
    start_at_iso: str,
    end_at_iso: str,
) -> dict[str, Any] | None:
    """
    SAFETY-CRITICAL: Validate that a requested booking slot is genuinely available.

    Returns None if the slot is valid, or a dict with {status, message} describing
    the rejection reason.

    Checks performed:
      1. Doctor exists and is active
      2. Requested time is in the future and within scheduling horizon
      3. Slot duration matches the doctor's configured slot_minutes
      4. Slot aligns with doctor's weekly availability template
      5. Slot does not overlap any doctor block
      6. Slot does not overlap any existing active appointment (full range check)
    """
    now = now_utc()
    horizon = now + timedelta(days=settings.SCHEDULING_HORIZON_DAYS)

    # -- Parse datetimes --
    try:
        start_dt = datetime.fromisoformat(start_at_iso.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_at_iso.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return {"status": "INVALID", "message": "Could not parse slot times."}

    if start_dt >= end_dt:
        return {"status": "INVALID", "message": "End time must be after start time."}

    # -- 1. Doctor must exist and be active --
    sb = get_supabase()
    doc_res = sb.table("doctors").select("id,is_active").eq("id", doctor_id).limit(1).execute()
    doc_data = getattr(doc_res, "data", None) or []
    if not doc_data:
        return {"status": "INVALID", "message": "Doctor not found."}
    if not doc_data[0]["is_active"]:
        return {"status": "INVALID", "message": "That doctor is not currently accepting appointments."}

    # -- 2. Must be in the future and within scheduling horizon --
    if start_dt <= now:
        return {"status": "INVALID", "message": "Cannot book a slot in the past."}
    if start_dt > horizon:
        return {"status": "INVALID", "message": "That date is beyond our scheduling window."}

    # -- 3 & 4. Slot must match a theoretical slot from the availability template --
    availability = _fetch_availability(doctor_id)
    if not availability:
        return {"status": "INVALID", "message": "Doctor has no availability configured."}

    # Generate theoretical slots for the day of the requested slot
    day_start_utc = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end_utc = day_start_utc + timedelta(days=2)  # pad to handle timezone offsets
    theoretical = _generate_theoretical_slots(availability, day_start_utc, day_end_utc)

    slot_match = False
    for t_start, t_end in theoretical:
        if t_start == start_dt and t_end == end_dt:
            slot_match = True
            break

    if not slot_match:
        return {
            "status": "INVALID",
            "message": "That time slot does not match the doctor's availability.",
        }

    # -- 5. Must not overlap any doctor block --
    blocks = _fetch_blocks(doctor_id, start_dt, end_dt)
    if _is_blocked(start_dt, end_dt, blocks):
        return {"status": "INVALID", "message": "The doctor is unavailable during that time."}

    # -- 6. Must not overlap any existing active appointment (full overlap check) --
    # SAFETY-CRITICAL: This checks for ANY overlap, not just identical start_at.
    overlap_check = _check_overlap(doctor_id, start_dt, end_dt)
    if overlap_check:
        return {"status": "TAKEN", "message": "That time slot conflicts with an existing appointment."}

    return None  # Slot is valid


def _check_overlap(
    doctor_id: str,
    start_dt: datetime,
    end_dt: datetime,
    exclude_appointment_id: str | None = None,
) -> bool:
    """
    SAFETY-CRITICAL: Check if a proposed time range overlaps any active appointment
    for the given doctor. Two intervals overlap when start_a < end_b AND start_b < end_a.

    Returns True if there IS an overlap (i.e. the slot is taken).
    """
    sb = get_supabase()
    query = (
        sb.table("appointments")
        .select("id")
        .eq("doctor_id", doctor_id)
        .neq("status", "CANCELLED")
        .lt("start_at", end_dt.isoformat())
        .gt("end_at", start_dt.isoformat())
        .limit(1)
    )
    if exclude_appointment_id:
        query = query.neq("id", exclude_appointment_id)
    res = query.execute()
    rows = getattr(res, "data", None) or []
    return len(rows) > 0


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

    day_raw = (preferred_day or "").strip().lower()
    bucket = parse_time_bucket(preferred_time)

    # Determine UTC search window
    if day_raw in NEXT_AVAILABLE_ALIASES:
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

    # Filter: not in past, not booked (overlap-aware), not blocked, matches bucket
    available = []
    for start, end in theoretical:
        if start < now:
            continue
        if _is_blocked(start, end, booked):
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
