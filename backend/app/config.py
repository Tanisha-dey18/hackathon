"""Application settings, loaded from environment variables (never hard-coded secrets)."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    # SQLite is the zero-dependency local fallback; Docker/Render use PostgreSQL.
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'sentinel.db').as_posix()}"
    redis_url: str | None = None

    jwt_secret: str = "change-me-in-production-please-32-bytes-min"
    jwt_expiry_minutes: int = 480
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Seeded demo accounts (synthetic environment only)
    seed_password: str = "SentinelDemo!2026"

    # PayPal Sandbox
    paypal_client_id: str | None = None
    paypal_client_secret: str | None = None
    paypal_base_url: str = "https://api-m.sandbox.paypal.com"
    paypal_webhook_id: str | None = None
    paypal_currency: str = "USD"

    # Groq LLM
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"

    model_dir: str = str(BACKEND_DIR / "model_store")
    rate_limit_per_minute: int = 120
    auto_seed: bool = True

    @property
    def paypal_configured(self) -> bool:
        return bool(self.paypal_client_id and self.paypal_client_secret)

    @property
    def groq_configured(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sqlalchemy_url(self) -> str:
        url = self.database_url
        # Render provides postgres:// URLs; SQLAlchemy 2 + psycopg3 needs an explicit driver.
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
