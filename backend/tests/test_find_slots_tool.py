import datetime as dt

import pytest

# Change this import if your tool file name/path differs
from app.api.routes.vapi_tools import slots as slots_tool
from app.services import time_nlp


# --------------------------
# Fake Supabase client
# --------------------------
class _Resp:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, table_data):
        self._data = table_data
        self._filters = []
        self._order_key = None
        self._order_desc = False
        self._limit = None

    def select(self, _cols):
        return self

    def eq(self, key, value):
        self._filters.append(("eq", key, value))
        return self

    def gte(self, key, value):
        self._filters.append(("gte", key, value))
        return self

    def lt(self, key, value):
        self._filters.append(("lt", key, value))
        return self

    def order(self, key, desc=False):
        self._order_key = key
        self._order_desc = desc
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        rows = list(self._data)

        def parse_iso(s: str) -> dt.datetime:
            return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))

        for t, k, v in self._filters:
            if t == "eq":
                rows = [r for r in rows if r.get(k) == v]
            elif t == "gte":
                vv = parse_iso(v)
                rows = [r for r in rows if parse_iso(r[k]) >= vv]
            elif t == "lt":
                vv = parse_iso(v)
                rows = [r for r in rows if parse_iso(r[k]) < vv]

        if self._order_key:
            rows.sort(key=lambda r: parse_iso(r[self._order_key]), reverse=self._order_desc)

        if self._limit is not None:
            rows = rows[: self._limit]

        return _Resp(rows)


class FakeSupabase:
    def __init__(self, table_rows):
        self._rows = table_rows

    def table(self, _name):
        return _Query(self._rows)


# --------------------------
# Fixtures
# --------------------------
def _fixed_now_utc():
    # Sunday Feb 22, 2026 18:00Z
    return dt.datetime(2026, 2, 22, 18, 0, 0, tzinfo=dt.timezone.utc)


@pytest.fixture(autouse=True)
def freeze_datetime_now(monkeypatch):
    # Freeze datetime.now(timezone.utc) inside time_nlp.clamp_not_in_past usage
    class _FrozenDateTime(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return _fixed_now_utc() if tz else _fixed_now_utc().replace(tzinfo=None)

    monkeypatch.setattr(time_nlp, "datetime", _FrozenDateTime, raising=False)


@pytest.fixture
def fake_doctor(monkeypatch):
    monkeypatch.setattr(
        slots_tool,
        "get_default_doctor",
        lambda: {"id": "doctor-1", "full_name": "Dr. Test"},
    )


# --------------------------
# Tests
# --------------------------
def test_find_slots_this_week_afternoon_returns_future_slots(monkeypatch, fake_doctor):
    # slots in UTC; 20:00Z and 22:00Z are 2PM and 4PM CT (afternoon)
    table_rows = [
        {
            "id": "s1",
            "doctor_id": "doctor-1",
            "status": "AVAILABLE",
            "start_at": "2026-02-23T20:00:00+00:00",
            "end_at": "2026-02-23T21:00:00+00:00",
        },
        {
            "id": "s2",
            "doctor_id": "doctor-1",
            "status": "AVAILABLE",
            "start_at": "2026-02-23T22:00:00+00:00",
            "end_at": "2026-02-23T23:00:00+00:00",
        },
    ]

    monkeypatch.setattr(slots_tool, "get_supabase", lambda: FakeSupabase(table_rows))

    out = slots_tool._find_slots({"preferred_day": "this week", "preferred_time": "afternoon"})
    assert out["status"] == "OK"
    assert len(out["slots"]) >= 1
    # Ensure labels are CT voice formatting
    assert out["slots"][0]["label"].startswith("Monday at")


def test_find_slots_next_available_day_afternoon_picks_earliest_bucket_day(monkeypatch, fake_doctor):
    # earliest slot overall is morning, but earliest AFTERNOON is next day
    table_rows = [
        # Feb 23 15:00Z = 9 AM CT (morning)
        {
            "id": "m1",
            "doctor_id": "doctor-1",
            "status": "AVAILABLE",
            "start_at": "2026-02-23T15:00:00+00:00",
            "end_at": "2026-02-23T16:00:00+00:00",
        },
        # Feb 24 20:00Z = 2 PM CT (afternoon) -> should be chosen for "afternoon"
        {
            "id": "a1",
            "doctor_id": "doctor-1",
            "status": "AVAILABLE",
            "start_at": "2026-02-24T20:00:00+00:00",
            "end_at": "2026-02-24T21:00:00+00:00",
        },
    ]

    monkeypatch.setattr(slots_tool, "get_supabase", lambda: FakeSupabase(table_rows))

    out = slots_tool._find_slots({"preferred_day": "next available day", "preferred_time": "afternoon"})
    assert out["status"] == "OK"
    assert out["slots"][0]["slot_id"] == "a1"
    assert out["slots"][0]["label"].endswith("2 PM")