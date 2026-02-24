import datetime as dt

import pytest

from app.services import time_nlp


def _fixed_now_ct():
    """
    Fixed time: Sunday Feb 22, 2026 12:00 CT.
    In UTC that's 18:00Z (since CT in Feb is UTC-6).
    """
    return dt.datetime(2026, 2, 22, 12, 0, 0, tzinfo=time_nlp.CT)


@pytest.fixture(autouse=True)
def freeze_now(monkeypatch):
    monkeypatch.setattr(time_nlp, "now_ct", _fixed_now_ct)


def test_parse_today_default():
    dr = time_nlp.parse_preferred_day_to_range("today")
    assert dr.start_date_ct == dt.date(2026, 2, 22)
    assert dr.end_date_ct == dt.date(2026, 2, 23)


def test_parse_empty_means_today():
    dr = time_nlp.parse_preferred_day_to_range("")
    assert dr.start_date_ct == dt.date(2026, 2, 22)
    assert dr.end_date_ct == dt.date(2026, 2, 23)


def test_parse_tomorrow():
    dr = time_nlp.parse_preferred_day_to_range("tomorrow")
    assert dr.start_date_ct == dt.date(2026, 2, 23)
    assert dr.end_date_ct == dt.date(2026, 2, 24)


def test_parse_weekday_name_next_occurrence_including_today():
    # Sunday Feb 22, 2026 -> "sunday" should resolve to today
    dr = time_nlp.parse_preferred_day_to_range("sunday")
    assert dr.start_date_ct == dt.date(2026, 2, 22)


def test_parse_weekday_name_future():
    # Sunday -> Monday should be Feb 23
    dr = time_nlp.parse_preferred_day_to_range("monday")
    assert dr.start_date_ct == dt.date(2026, 2, 23)


def test_parse_next_weekday():
    dr = time_nlp.parse_preferred_day_to_range("next monday")
    # "next monday" strictly after today => Feb 23, 2026 (since today is Sunday)
    assert dr.start_date_ct == dt.date(2026, 2, 23)


def test_parse_this_week_is_next_7_days():
    dr = time_nlp.parse_preferred_day_to_range("this week")
    assert dr.start_date_ct == dt.date(2026, 2, 22)
    assert dr.end_date_ct == dt.date(2026, 3, 1)  # 7 days window


def test_parse_next_week_is_following_7_days():
    dr = time_nlp.parse_preferred_day_to_range("next week")
    assert dr.start_date_ct == dt.date(2026, 3, 1)
    assert dr.end_date_ct == dt.date(2026, 3, 8)


def test_parse_weekend_from_sunday():
    # From Sunday Feb 22, next weekend is Sat Feb 28 + Sun Mar 1
    dr = time_nlp.parse_preferred_day_to_range("weekend")
    assert dr.start_date_ct == dt.date(2026, 2, 28)
    assert dr.end_date_ct == dt.date(2026, 3, 2)


def test_parse_mmdd_date():
    dr = time_nlp.parse_preferred_day_to_range("2/24")
    assert dr.start_date_ct == dt.date(2026, 2, 24)
    assert dr.end_date_ct == dt.date(2026, 2, 25)


def test_parse_month_name_date():
    dr = time_nlp.parse_preferred_day_to_range("feb 24")
    assert dr.start_date_ct == dt.date(2026, 2, 24)


def test_preferred_time_bucket():
    assert time_nlp.preferred_time_bucket("morning") == "morning"
    assert time_nlp.preferred_time_bucket("afternoon") == "afternoon"
    assert time_nlp.preferred_time_bucket("evening") == "evening"
    assert time_nlp.preferred_time_bucket("any") == "any"
    assert time_nlp.preferred_time_bucket("") == "any"
    assert time_nlp.preferred_time_bucket("no preference") == "any"


def test_range_to_utc_bounds_today():
    dr = time_nlp.parse_preferred_day_to_range("today")
    start_utc, end_utc = time_nlp.range_to_utc_bounds(dr)
    # Feb 22 00:00 CT is Feb 22 06:00 UTC (standard time)
    assert start_utc == dt.datetime(2026, 2, 22, 6, 0, 0, tzinfo=dt.timezone.utc)
    assert end_utc == dt.datetime(2026, 2, 23, 6, 0, 0, tzinfo=dt.timezone.utc)


def test_slot_in_bucket_afternoon_ct():
    # 2026-02-23 20:00Z = 14:00 CT (afternoon)
    assert time_nlp.slot_in_bucket("2026-02-23T20:00:00+00:00", "afternoon") is True
    # 2026-02-23 15:00Z = 09:00 CT (morning), not afternoon
    assert time_nlp.slot_in_bucket("2026-02-23T15:00:00+00:00", "afternoon") is False


def test_format_voice_from_iso_ct():
    # 2026-02-23 20:00Z => Monday 2 PM CT
    s = time_nlp.format_voice_from_iso("2026-02-23T20:00:00+00:00")
    assert s == "Monday at 2 PM"