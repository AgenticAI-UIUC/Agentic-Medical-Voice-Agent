from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from app.config import settings

Bucket = Literal["morning", "afternoon", "any"]

CLINIC_TZ = ZoneInfo(settings.CLINIC_TIMEZONE)

BUCKETS: dict[Bucket, tuple[time, time]] = {
    "morning": (time(8, 0), time(12, 0)),
    "afternoon": (time(12, 0), time(17, 0)),
    "any": (time(0, 0), time(23, 59, 59)),
}

WEEKDAY_MAP: dict[str, int] = {
    "mon": 0, "monday": 0,
    "tue": 1, "tues": 1, "tuesday": 1,
    "wed": 2, "weds": 2, "wednesday": 2,
    "thu": 3, "thur": 3, "thurs": 3, "thursday": 3,
    "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
}

MONTH_MAP: dict[str, int] = {
    "jan": 1, "january": 1, "feb": 2, "february": 2,
    "mar": 3, "march": 3, "apr": 4, "april": 4,
    "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_clinic() -> datetime:
    return now_utc().astimezone(CLINIC_TZ)


def _normalize(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^\w\s/:-]", "", s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\b(\d{1,2})(st|nd|rd|th)\b", r"\1", s)
    s = s.replace("of ", "")
    return s.strip()


# ------------------------------------------------------------------
# Date range parsing
# ------------------------------------------------------------------

@dataclass(frozen=True)
class DayRange:
    start_date: date  # inclusive
    end_date: date    # exclusive


def _next_weekday(from_date: date, target: int, strictly_after: bool) -> date:
    d = from_date + timedelta(days=1) if strictly_after else from_date
    days_ahead = (target - d.weekday()) % 7
    return d + timedelta(days=days_ahead)


def _parse_mmdd(s: str, year: int) -> date | None:
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", s)
    if not m:
        return None
    mm, dd = int(m.group(1)), int(m.group(2))
    yy = m.group(3)
    y = int(yy) + (2000 if int(yy) < 100 else 0) if yy else year
    try:
        return date(y, mm, dd)
    except ValueError:
        return None


def _parse_month_day(s: str, year: int) -> date | None:
    """Handles 'feb 24' and '24 feb' patterns."""
    for pattern in [r"([a-z]+)\s+(\d{1,2})(?:\s+(\d{2,4}))?",
                    r"(\d{1,2})\s+([a-z]+)(?:\s+(\d{2,4}))?"]:
        m = re.fullmatch(pattern, s)
        if not m:
            continue
        g1, g2, g3 = m.group(1), m.group(2), m.group(3)
        if g1.isdigit():
            dd, mon_str = int(g1), g2
        else:
            mon_str, dd = g1, int(g2)
        mm = MONTH_MAP.get(mon_str)
        if not mm:
            continue
        y = int(g3) + (2000 if int(g3) < 100 else 0) if g3 else year
        try:
            return date(y, mm, dd)
        except ValueError:
            continue
    return None


def parse_preferred_day(preferred_day: str) -> DayRange:
    s = _normalize(preferred_day)
    today = now_clinic().date()

    if s in ("", "today", "tod"):
        return DayRange(today, today + timedelta(days=1))

    if s in ("tomorrow", "tmr", "tommorow"):
        d = today + timedelta(days=1)
        return DayRange(d, d + timedelta(days=1))

    if s in ("this week", "thisweek"):
        return DayRange(today, today + timedelta(days=7))

    if s in ("next week", "nextweek"):
        start = today + timedelta(days=7)
        return DayRange(start, start + timedelta(days=7))

    if s in ("weekend", "this weekend"):
        days_until_sat = (5 - today.weekday()) % 7
        sat = today + timedelta(days=days_until_sat)
        return DayRange(sat, sat + timedelta(days=2))

    # "next monday" etc.
    m = re.fullmatch(r"next\s+([a-z]+)", s)
    if m:
        w = WEEKDAY_MAP.get(m.group(1))
        if w is not None:
            d = _next_weekday(today, w, strictly_after=True)
            return DayRange(d, d + timedelta(days=1))

    # bare weekday name
    if s in WEEKDAY_MAP:
        d = _next_weekday(today, WEEKDAY_MAP[s], strictly_after=False)
        return DayRange(d, d + timedelta(days=1))

    # numeric: 2/24 or 02/24/2026
    parsed = _parse_mmdd(s, today.year)
    if parsed:
        return DayRange(parsed, parsed + timedelta(days=1))

    # month name: "feb 24" / "24 feb"
    parsed2 = _parse_month_day(s, today.year)
    if parsed2:
        return DayRange(parsed2, parsed2 + timedelta(days=1))

    # N weeks
    m = re.fullmatch(r"(\d+)\s*weeks?", s)
    if m:
        weeks = int(m.group(1))
        return DayRange(today, today + timedelta(weeks=weeks))

    # fallback
    return DayRange(today, today + timedelta(days=1))


def parse_time_bucket(preferred_time: str) -> Bucket:
    s = _normalize(preferred_time)
    if s in ("", "any", "anything", "whenever", "no preference"):
        return "any"
    if "morn" in s:
        return "morning"
    if "after" in s or s == "pm":
        return "afternoon"
    return "any"


# ------------------------------------------------------------------
# Slot filtering / formatting
# ------------------------------------------------------------------

def day_range_to_utc(dr: DayRange) -> tuple[datetime, datetime]:
    start = datetime.combine(dr.start_date, time.min, tzinfo=CLINIC_TZ)
    end = datetime.combine(dr.end_date, time.min, tzinfo=CLINIC_TZ)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def is_in_bucket(start_utc: datetime, bucket: Bucket) -> bool:
    if bucket == "any":
        return True
    local = start_utc.astimezone(CLINIC_TZ)
    b_start, b_end = BUCKETS[bucket]
    return b_start <= local.time() < b_end


def format_for_voice(dt_utc: datetime) -> str:
    """Format like 'Monday, March 31 at 2 PM'."""
    local = dt_utc.astimezone(CLINIC_TZ)
    hour = local.strftime("%I").lstrip("0") or "12"
    ampm = local.strftime("%p")
    return f"{local.strftime('%A')}, {local.strftime('%B')} {local.day} at {hour} {ampm}"


def format_date_for_voice(dt_utc: datetime) -> str:
    """Format like 'Monday, February 24'."""
    local = dt_utc.astimezone(CLINIC_TZ)
    return local.strftime("%A, %B %-d")
