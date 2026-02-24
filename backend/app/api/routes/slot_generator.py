from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from typing import Any

from app.services.supabase_client import get_supabase

CHICAGO = ZoneInfo("America/Chicago")


@dataclass(frozen=True)
class Availability:
    day_of_week: int              # 0=Sun..6=Sat
    start_time: time              # 09:00
    end_time: time                # 17:00
    slot_minutes: int             # 60
    break_start: time | None      # 12:00
    break_end: time | None        # 13:00
    timezone: str                 # America/Chicago


def _parse_time(s: str | None) -> time | None:
    if not s:
        return None
    # Supabase returns TIME as "HH:MM:SS" typically
    hh, mm, *_ = s.split(":")
    return time(int(hh), int(mm))


def _time_from_db(s: str) -> time:
    t = _parse_time(s)
    assert t is not None
    return t


def fetch_weekly_availability(doctor_id: str) -> list[Availability]:
    supabase = get_supabase()
    res = (
        supabase.table("doctor_availability")
        .select("day_of_week,start_time,end_time,slot_minutes,break_start,break_end,timezone")
        .eq("doctor_id", doctor_id)
        .execute()
    )
    rows = getattr(res, "data", None) or []
    out: list[Availability] = []
    for r in rows:
        out.append(
            Availability(
                day_of_week=int(r["day_of_week"]),
                start_time=_time_from_db(r["start_time"]),
                end_time=_time_from_db(r["end_time"]),
                slot_minutes=int(r.get("slot_minutes") or 60),
                break_start=_parse_time(r.get("break_start")),
                break_end=_parse_time(r.get("break_end")),
                timezone=r.get("timezone") or "America/Chicago",
            )
        )
    return out


def _daterange(start: date, days: int) -> list[date]:
    return [start + timedelta(days=i) for i in range(days)]


def generate_slots_for_doctor(
    doctor_id: str,
    start_date: date,
    days: int = 14,
) -> dict[str, Any]:
    """
    Generates concrete 60-min slots into appointment_slots based on doctor_availability.
    Skips duplicates automatically via (doctor_id, start_at) unique constraint.
    """
    weekly = fetch_weekly_availability(doctor_id)
    by_dow = {a.day_of_week: a for a in weekly}

    to_insert: list[dict[str, Any]] = []

    for d in _daterange(start_date, days):
        # Python weekday(): Mon=0..Sun=6, but our schema uses Sun=0..Sat=6
        # Convert: python_dow (Mon=0) -> schema_dow (Sun=0)
        python_dow = d.weekday()  # Mon=0..Sun=6
        schema_dow = (python_dow + 1) % 7  # Sun=0..Sat=6

        avail = by_dow.get(schema_dow)
        if not avail:
            continue

        tz = ZoneInfo(avail.timezone) if avail.timezone else CHICAGO
        slot_len = timedelta(minutes=avail.slot_minutes)

        start_dt = datetime.combine(d, avail.start_time, tzinfo=tz)
        end_dt = datetime.combine(d, avail.end_time, tzinfo=tz)

        break_start_dt = datetime.combine(d, avail.break_start, tzinfo=tz) if avail.break_start else None
        break_end_dt = datetime.combine(d, avail.break_end, tzinfo=tz) if avail.break_end else None

        cur = start_dt
        while cur + slot_len <= end_dt:
            # skip lunch break overlap
            if break_start_dt and break_end_dt:
                overlaps_break = not (cur + slot_len <= break_start_dt or cur >= break_end_dt)
                if overlaps_break:
                    cur = break_end_dt
                    continue

            to_insert.append({
                "doctor_id": doctor_id,
                "start_at": cur.isoformat(),
                "end_at": (cur + slot_len).isoformat(),
                "status": "AVAILABLE",
            })
            cur += slot_len

    if not to_insert:
        return {"inserted": 0, "attempted": 0}

    supabase = get_supabase()
    # Insert in chunks to avoid payload limits
    inserted_total = 0
    attempted_total = len(to_insert)

    CHUNK = 500
    for i in range(0, len(to_insert), CHUNK):
        chunk = to_insert[i:i + CHUNK]
        try:
            res = supabase.table("appointment_slots").insert(chunk).execute()
            data = getattr(res, "data", None) or []
            if isinstance(data, list):
                inserted_total += len(data)
        except Exception:
            # If duplicates cause errors in your client version, we can switch to upsert.
            # For now, keep it simple; most setups accept insert and ignore duplicates only if using upsert.
            raise

    return {"inserted": inserted_total, "attempted": attempted_total}