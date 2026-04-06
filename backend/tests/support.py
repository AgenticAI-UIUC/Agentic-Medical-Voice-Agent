from __future__ import annotations

from types import SimpleNamespace
from typing import Any


class MockQuery:
    def __init__(self, *, data: Any = None, error: Exception | None = None) -> None:
        self.data = [] if data is None else data
        self.error = error
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.inserted_rows: list[dict[str, Any]] = []
        self.updated_rows: list[dict[str, Any]] = []

    def _record(self, name: str, *args: Any, **kwargs: Any) -> MockQuery:
        self.calls.append((name, args, kwargs))
        return self

    def select(self, *args: Any, **kwargs: Any) -> MockQuery:
        return self._record("select", *args, **kwargs)

    def eq(self, *args: Any, **kwargs: Any) -> MockQuery:
        return self._record("eq", *args, **kwargs)

    def neq(self, *args: Any, **kwargs: Any) -> MockQuery:
        return self._record("neq", *args, **kwargs)

    def gte(self, *args: Any, **kwargs: Any) -> MockQuery:
        return self._record("gte", *args, **kwargs)

    def gt(self, *args: Any, **kwargs: Any) -> MockQuery:
        return self._record("gt", *args, **kwargs)

    def lt(self, *args: Any, **kwargs: Any) -> MockQuery:
        return self._record("lt", *args, **kwargs)

    def ilike(self, *args: Any, **kwargs: Any) -> MockQuery:
        return self._record("ilike", *args, **kwargs)

    def limit(self, *args: Any, **kwargs: Any) -> MockQuery:
        return self._record("limit", *args, **kwargs)

    def order(self, *args: Any, **kwargs: Any) -> MockQuery:
        return self._record("order", *args, **kwargs)

    def insert(self, row: dict[str, Any]) -> MockQuery:
        self.inserted_rows.append(row)
        return self._record("insert", row)

    def update(self, row: dict[str, Any]) -> MockQuery:
        self.updated_rows.append(row)
        return self._record("update", row)

    def execute(self) -> SimpleNamespace:
        self.calls.append(("execute", (), {}))
        if self.error is not None:
            raise self.error
        return SimpleNamespace(data=self.data)


class MockSupabase:
    def __init__(
        self,
        *,
        tables: dict[str, list[MockQuery]] | None = None,
        rpcs: dict[str, list[MockQuery]] | None = None,
    ) -> None:
        self.tables = {name: list(queue) for name, queue in (tables or {}).items()}
        self.rpcs = {name: list(queue) for name, queue in (rpcs or {}).items()}
        self.table_calls: list[str] = []
        self.rpc_calls: list[tuple[str, dict[str, Any]]] = []

    def table(self, name: str) -> MockQuery:
        self.table_calls.append(name)
        queue = self.tables.get(name)
        if not queue:
            raise AssertionError(f"Unexpected table access: {name}")
        return queue.pop(0)

    def rpc(self, name: str, params: dict[str, Any]) -> MockQuery:
        self.rpc_calls.append((name, params))
        queue = self.rpcs.get(name)
        if not queue:
            raise AssertionError(f"Unexpected RPC access: {name}")
        return queue.pop(0)


def make_tool_payload(
    args: dict[str, Any],
    *,
    tool_call_id: str = "tool-1",
    call_id: str = "call-1",
) -> dict[str, Any]:
    return {
        "message": {
            "toolCalls": [
                {
                    "id": tool_call_id,
                    "function": {"arguments": args},
                }
            ],
            "call": {"id": call_id},
        }
    }
