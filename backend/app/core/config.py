import secrets
from typing import Annotated, Any, Literal

from pydantic import AnyUrl, BeforeValidator, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",") if i.strip()]
    if isinstance(v, (list, str)):
        return v
    raise ValueError(v)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",  # root-level .env (one level above backend/)
        env_ignore_empty=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "FastAPI App"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"
    API_V1_STR: str = "/api/v1"

    # Auth settings
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # 1 hour

    FRONTEND_HOST: str = "http://localhost:5173"
    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    @computed_field
    @property
    def is_local(self) -> bool:
        return self.ENVIRONMENT == "local"

    @computed_field
    @property
    def all_cors_origins(self) -> list[str]:
        origins = [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS]
        frontend = self.FRONTEND_HOST.rstrip("/")
        if frontend not in origins:
            origins.append(frontend)
        return origins

    @model_validator(mode="after")
    def validate_security(self) -> "Settings":
        weak_values = {
            "changethis",
            "secret",
            "password",
            "123456",
            "dev",
            "test",
        }

        # PyJWT warns for short HMAC keys (<32 bytes) when using HS256.
        secret_too_short = len(self.SECRET_KEY.encode("utf-8")) < 32
        secret_is_weak_literal = self.SECRET_KEY.lower() in weak_values

        if self.ENVIRONMENT != "local" and (secret_too_short or secret_is_weak_literal):
            raise ValueError(
                "SECRET_KEY is too weak for non-local environment. "
                "Use a long random value (recommended >= 32 bytes)."
            )

        return self


settings = Settings()
