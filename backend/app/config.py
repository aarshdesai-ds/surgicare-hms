"""Application configuration loaded from environment / .env file."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings.

    Values come from environment variables or a local `.env` file. See
    `.env.example` for the full list and where to find each value in Supabase.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/postgres"

    # Supabase
    supabase_jwt_secret: str = "change-me-super-secret"
    supabase_url: str = ""
    supabase_service_role_key: str = ""

    # App
    environment: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Razorpay (payments). Leave blank to run without online payments.
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    # Where a paid link should send the payer back (their own phone browser).
    razorpay_callback_url: str = "http://localhost:5173/billing"

    @property
    def razorpay_configured(self) -> bool:
        return bool(self.razorpay_key_id and self.razorpay_key_secret)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor (instantiate once per process)."""
    return Settings()


settings = get_settings()
