from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_ignore_empty=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "Medical Voice Agent"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"
    API_V1_STR: str = "/api/v1"

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # Clinic defaults
    CLINIC_TIMEZONE: str = "America/Chicago"
    SCHEDULING_HORIZON_DAYS: int = 14

    # Vapi webhook secret (optional — set to enforce signature check)
    VAPI_WEBHOOK_SECRET: str = ""

    # CORS
    FRONTEND_HOST: str = "http://localhost:5173"

    @property
    def is_local(self) -> bool:
        return self.ENVIRONMENT == "local"


settings = Settings()
