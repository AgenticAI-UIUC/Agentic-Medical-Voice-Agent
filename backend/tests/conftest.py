"""Shared test fixtures and fake Supabase helpers."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock


def utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def future(hours: int = 48) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours)


def make_payload(args: dict[str, Any] | None = None, call_id: str = "call-test-456") -> dict[str, Any]:
    return {
        "message": {
            "toolCalls": [
                {"id": "tc-1", "function": {"arguments": args or {}}},
            ],
            "call": {"id": call_id},
        }
    }


class FakeQueryBuilder:
    def __init__(self, data: list[dict] | None = None, raise_on_insert: Exception | None = None):
        self._data = data or []
        self._raise_on_insert = raise_on_insert

    def __getattr__(self, name):
        if name in ("select", "eq", "neq", "gt", "gte", "lt", "lte",
                     "order", "limit", "update", "delete", "ilike"):
            return lambda *_a, **_kw: self
        raise AttributeError(name)

    def insert(self, row):
        if self._raise_on_insert:
            raise self._raise_on_insert
        self._last_inserted = row
        self._data = [{"id": str(uuid.uuid4()), **row}]
        return self

    def execute(self):
        resp = MagicMock()
        resp.data = self._data
        return resp


class FakeSupabase:
    def __init__(self, tables: dict[str, FakeQueryBuilder] | None = None):
        self._tables = tables or {}

    def table(self, name: str) -> FakeQueryBuilder:
        return self._tables.get(name, FakeQueryBuilder())


class SequentialQueryBuilder(FakeQueryBuilder):
    """Returns different data on each execute() call."""
    def __init__(self, responses: list[list[dict]]):
        super().__init__([])
        self._responses = responses
        self._call = 0

    def execute(self):
        resp = MagicMock()
        idx = min(self._call, len(self._responses) - 1)
        resp.data = self._responses[idx]
        self._call += 1
        return resp
