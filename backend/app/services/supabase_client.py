from supabase import create_client
from supabase.lib.client_options import SyncClientOptions

from app.core.config import settings


def get_supabase():
    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY,
        options=SyncClientOptions(auto_refresh_token=False, persist_session=False),
    )
