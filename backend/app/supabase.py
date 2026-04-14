from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions

from app.config import settings

_client: Client | None = None
_POSTGREST_TIMEOUT_SECONDS = 8


def get_supabase() -> Client:
    global _client
    if _client is None:
        _client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY,
            options=SyncClientOptions(
                auto_refresh_token=False,
                persist_session=False,
                # Vapi expects tool webhooks to answer quickly, so keep DB calls
                # well under its timeout and let the assistant retry cleanly.
                postgrest_client_timeout=_POSTGREST_TIMEOUT_SECONDS,
            ),
        )
    return _client
