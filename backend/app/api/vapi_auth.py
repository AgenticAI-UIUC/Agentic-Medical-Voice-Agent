"""Shared VAPI webhook authentication.

When VAPI_WEBHOOK_SECRET is set, all incoming VAPI requests (both tool calls
and lifecycle events) must include a matching ``x-vapi-secret`` header.

When the secret is empty (local dev), verification is skipped.
"""
from __future__ import annotations

import hmac
import logging

from fastapi import HTTPException, Request

from app.config import settings

logger = logging.getLogger(__name__)


async def verify_vapi_secret(request: Request) -> None:
    """FastAPI dependency — raises 401 if the secret doesn't match."""
    secret = settings.VAPI_WEBHOOK_SECRET
    if not secret:
        return  # no secret configured → skip (local dev)

    token = request.headers.get("x-vapi-secret", "")
    if not hmac.compare_digest(token, secret):
        logger.warning("VAPI auth failed from %s", request.client.host if request.client else "unknown")
        raise HTTPException(status_code=401, detail="Unauthorized")
