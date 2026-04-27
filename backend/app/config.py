import json
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

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
    FRONTEND_HOST: str = "http://localhost:3000"
    BACKEND_CORS_ORIGINS: Annotated[list[str], NoDecode] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if isinstance(value, str) and value.startswith("["):
            decoded = json.loads(value)
            if not isinstance(decoded, list):
                raise ValueError("BACKEND_CORS_ORIGINS must be a list")
            return [str(origin).strip() for origin in decoded if str(origin).strip()]
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def all_cors_origins(self) -> list[str]:
        origins = [self.FRONTEND_HOST, *self.BACKEND_CORS_ORIGINS]
        return list(dict.fromkeys(origin for origin in origins if origin))

    @property
    def is_local(self) -> bool:
        return self.ENVIRONMENT == "local"


settings = Settings()
