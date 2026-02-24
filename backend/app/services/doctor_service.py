from __future__ import annotations

from typing import Any

from app.services.supabase_client import get_supabase


def get_default_doctor() -> dict[str, Any] | None:
    """
    Return the first active doctor (v1: single-doctor clinic).
    """
    supabase = get_supabase()
    res = (
        supabase.table("doctors")
        .select("id,full_name,is_active")
        .eq("is_active", True)
        .order("created_at", desc=False)
        .limit(1)
        .execute()
    )
    data = getattr(res, "data", None) or []
    return data[0] if data else None