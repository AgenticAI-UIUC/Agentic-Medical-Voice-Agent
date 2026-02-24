from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal, Optional
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")

Bucket = Literal["morning", "afternoon", "any"]

# You can tune these to match your clinic hours
BUCKETS_CT: dict[str, tuple[time, time]] = {
    "morning": (time(8, 0), time(12, 0)),
    "afternoon": (time(12, 0), time(17, 0)),
    "any": (time(0, 0), time(23, 59, 59)),
}

WEEKDAY_MAP = {
    "mon": 0, "monday": 0,
    "tue": 1, "tues": 1, "tuesday": 1,
    "wed": 2, "weds": 2, "wednesday": 2,
    "thu": 3, "thur": 3, "thurs": 3, "thursday": 3,
    "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
}

MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def now_ct() -> datetime:
    return datetime.now(timezone.utc).astimezone(CT)


def _strip_ordinal_tokens(s: str) -> str:
    # "26th" -> "26", "1st" -> "1", "2nd" -> "2", "3rd" -> "3"
    return re.sub(r"\b(\d{1,2})(st|nd|rd|th)\b", r"\1", s)


def _normalize(s: str) -> str:
    """
    Normalize common speech-to-text messiness:
    - lowercase
    - remove punctuation
    - collapse spaces
    - convert ordinals: 26th -> 26
    """
    s = (s or "").strip().lower()
    s = re.sub(r"[^\w\s/:-]", "", s)  # keep / :- for dates
    s = re.sub(r"\s+", " ", s)
    s = _strip_ordinal_tokens(s)
    # common filler words
    s = s.replace("of ", "")  # "26th of february" -> "26 february"
    return s.strip()


def _parse_mmdd(s: str, year: int) -> Optional[date]:
    # accepts 2/24 or 02/24 or 2/24/2026
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", s)
    if not m:
        return None
    mm = int(m.group(1))
    dd = int(m.group(2))
    yy = m.group(3)
    if yy:
        y = int(yy)
        if y < 100:
            y += 2000
    else:
        y = year
    try:
        return date(y, mm, dd)
    except ValueError:
        return None


def _parse_month_name_date(s: str, year: int) -> Optional[date]:
    # accepts "feb 24" / "february 24" / "feb 24 2026"
    m = re.fullmatch(r"([a-z]+)\s+(\d{1,2})(?:\s+(\d{2,4}))?", s)
    if not m:
        return None
    mon = m.group(1)
    dd = int(m.group(2))
    yy = m.group(3)
    mm = MONTH_MAP.get(mon)
    if not mm:
        return None
    if yy:
        y = int(yy)
        if y < 100:
            y += 2000
    else:
        y = year
    try:
        return date(y, mm, dd)
    except ValueError:
        return None


def _parse_day_month_name_date(s: str, year: int) -> Optional[date]:
    # accepts "26 feb" / "26 february" / "26 feb 2026"
    m = re.fullmatch(r"(\d{1,2})\s+([a-z]+)(?:\s+(\d{2,4}))?", s)
    if not m:
        return None
    dd = int(m.group(1))
    mon = m.group(2)
    yy = m.group(3)

    mm = MONTH_MAP.get(mon)
    if not mm:
        return None

    if yy:
        y = int(yy)
        if y < 100:
            y += 2000
    else:
        y = year

    try:
        return date(y, mm, dd)
    except ValueError:
        return None


@dataclass(frozen=True)
class DayRange:
    """
    A preferred-day resolution as a date range in CT (inclusive start, exclusive end).
    """
    start_date_ct: date
    end_date_ct: date  # exclusive


def _next_weekday(from_date: date, target_weekday: int, strictly_after: bool) -> date:
    """
    Return the next date that has weekday == target_weekday.
    If strictly_after is False, can return today if it matches.
    """
    d = from_date
    if strictly_after:
        d = d + timedelta(days=1)
    days_ahead = (target_weekday - d.weekday()) % 7
    return d + timedelta(days=days_ahead)


def parse_preferred_day_to_range(preferred_day: str) -> DayRange:
    """
    Converts user's day phrase into a CT date range.
    Does NOT handle "next available day/date" (that must query DB).
    """
    s = _normalize(preferred_day)
    today = now_ct().date()

    if s in ("", "today", "tod"):
        return DayRange(today, today + timedelta(days=1))

    if s in ("tomorrow", "tmr", "tommorow"):
        d = today + timedelta(days=1)
        return DayRange(d, d + timedelta(days=1))

    # "this week" / "next week" (rolling windows)
    if s in ("this week", "thisweek"):
        return DayRange(today, today + timedelta(days=7))

    if s in ("next week", "nextweek"):
        start = today + timedelta(days=7)
        return DayRange(start, start + timedelta(days=7))

    # weekend
    if s in ("weekend", "this weekend", "thisweekend"):
        wd = today.weekday()
        days_until_sat = (5 - wd) % 7
        sat = today + timedelta(days=days_until_sat)
        return DayRange(sat, sat + timedelta(days=2))

    # weekdays (roughly next 7 days)
    if s in ("weekday", "weekdays", "this weekday", "thisweekdays"):
        return DayRange(today, today + timedelta(days=7))

    # "next monday"
    m = re.fullmatch(r"next\s+([a-z]+)", s)
    if m:
        w = WEEKDAY_MAP.get(m.group(1))
        if w is not None:
            d = _next_weekday(today, w, strictly_after=True)
            return DayRange(d, d + timedelta(days=1))

    # weekday names like "friday"
    if s in WEEKDAY_MAP:
        w = WEEKDAY_MAP[s]
        d = _next_weekday(today, w, strictly_after=False)
        return DayRange(d, d + timedelta(days=1))

    # numeric dates: 2/24 or 02/24/2026
    parsed = _parse_mmdd(s, today.year)
    if parsed:
        return DayRange(parsed, parsed + timedelta(days=1))

    # month name dates: "feb 24"
    parsed2 = _parse_month_name_date(s, today.year)
    if parsed2:
        return DayRange(parsed2, parsed2 + timedelta(days=1))

    # day month dates: "24 feb" / "26th feb"
    parsed3 = _parse_day_month_name_date(s, today.year)
    if parsed3:
        return DayRange(parsed3, parsed3 + timedelta(days=1))

    # fallback: treat as today
    return DayRange(today, today + timedelta(days=1))


def preferred_time_bucket(preferred_time: str) -> Bucket:
    s = _normalize(preferred_time)
    if s in ("", "any", "anything", "whenever", "no preference", "nopreference"):
        return "any"
    if "morn" in s:
        return "morning"
    if "after" in s or s == "pm":
        return "afternoon"
    return "any"


def range_to_utc_bounds(dr: DayRange) -> tuple[datetime, datetime]:
    """
    Convert CT date range to UTC datetime bounds (inclusive start, exclusive end).
    """
    start_ct = datetime(
        dr.start_date_ct.year, dr.start_date_ct.month, dr.start_date_ct.day,
        0, 0, 0, tzinfo=CT
    )
    end_ct = datetime(
        dr.end_date_ct.year, dr.end_date_ct.month, dr.end_date_ct.day,
        0, 0, 0, tzinfo=CT
    )
    return start_ct.astimezone(timezone.utc), end_ct.astimezone(timezone.utc)


def slot_in_bucket(start_at_iso: str, bucket: Bucket) -> bool:
    """
    start_at_iso is expected in ISO-ish string with timezone or 'Z'.
    """
    if bucket == "any":
        return True
    s = start_at_iso.replace("Z", "+00:00")
    dt_utc = datetime.fromisoformat(s)
    ct = dt_utc.astimezone(CT)
    b_start, b_end = BUCKETS_CT[bucket]
    t = ct.time()
    return (t >= b_start) and (t < b_end)


def clamp_not_in_past(start_iso: str) -> bool:
    """
    True if slot start is >= now (UTC).
    """
    s = start_iso.replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    return dt >= datetime.now(timezone.utc)


def format_voice_from_iso(start_at_iso: str) -> str:
    """
    Format like: 'Monday at 2 PM' in America/Chicago.
    Windows-safe (does not use %-I).
    """
    s = start_at_iso.replace("Z", "+00:00")
    dt_utc = datetime.fromisoformat(s)
    dt_ct = dt_utc.astimezone(CT)
    hour_12 = dt_ct.strftime("%I").lstrip("0") or "12"
    ampm = dt_ct.strftime("%p")
    return f"{dt_ct.strftime('%A')} at {hour_12} {ampm}"