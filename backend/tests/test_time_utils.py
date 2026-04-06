from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.services import time_utils


FIXED_CLINIC_NOW = datetime(2026, 4, 6, 9, 30, tzinfo=ZoneInfo("America/Chicago"))


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time_utils, "now_clinic", lambda: FIXED_CLINIC_NOW)


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("today", time_utils.DayRange(date(2026, 4, 6), date(2026, 4, 7))),
        ("tomorrow", time_utils.DayRange(date(2026, 4, 7), date(2026, 4, 8))),
        ("weekend", time_utils.DayRange(date(2026, 4, 11), date(2026, 4, 13))),
        ("friday", time_utils.DayRange(date(2026, 4, 10), date(2026, 4, 11))),
        ("next monday", time_utils.DayRange(date(2026, 4, 13), date(2026, 4, 14))),
        ("4/18", time_utils.DayRange(date(2026, 4, 18), date(2026, 4, 19))),
        ("april 18", time_utils.DayRange(date(2026, 4, 18), date(2026, 4, 19))),
        ("18 apr", time_utils.DayRange(date(2026, 4, 18), date(2026, 4, 19))),
        ("2 weeks", time_utils.DayRange(date(2026, 4, 6), date(2026, 4, 20))),
        ("something vague", time_utils.DayRange(date(2026, 4, 6), date(2026, 4, 7))),
    ],
)
def test_parse_preferred_day(raw_value: str, expected: time_utils.DayRange) -> None:
    assert time_utils.parse_preferred_day(raw_value) == expected


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("", "any"),
        ("whenever", "any"),
        ("morning please", "morning"),
        ("afternoon", "afternoon"),
        ("pm", "afternoon"),
        ("evening", "any"),
    ],
)
def test_parse_time_bucket(raw_value: str, expected: time_utils.Bucket) -> None:
    assert time_utils.parse_time_bucket(raw_value) == expected


def test_day_range_to_utc_respects_clinic_timezone() -> None:
    start_utc, end_utc = time_utils.day_range_to_utc(
        time_utils.DayRange(date(2026, 4, 6), date(2026, 4, 7))
    )

    assert start_utc == datetime(2026, 4, 6, 5, 0, tzinfo=timezone.utc)
    assert end_utc == datetime(2026, 4, 7, 5, 0, tzinfo=timezone.utc)


def test_is_in_bucket_uses_local_clinic_time() -> None:
    morning_slot = datetime(2026, 4, 6, 15, 0, tzinfo=timezone.utc)
    afternoon_slot = datetime(2026, 4, 6, 18, 0, tzinfo=timezone.utc)

    assert time_utils.is_in_bucket(morning_slot, "morning") is True
    assert time_utils.is_in_bucket(afternoon_slot, "morning") is False
    assert time_utils.is_in_bucket(afternoon_slot, "afternoon") is True


def test_formatting_helpers_return_voice_friendly_strings() -> None:
    dt_utc = datetime(2026, 4, 6, 19, 0, tzinfo=timezone.utc)

    assert time_utils.format_for_voice(dt_utc) == "Monday, April 6 at 2 PM"
    assert time_utils.format_date_for_voice(dt_utc) == "Monday, April 6"
