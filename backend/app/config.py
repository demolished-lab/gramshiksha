from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Gramshiksha API"
    # Dev default: local SQLite. Production: Neon Postgres via DATABASE_URL.
    database_url: str = "sqlite:///./gramshiksha.db"
    # Keep in sync when changing secret handling.
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days, low-bandwidth friendly
    cors_origins: list[str] = ["http://localhost:5174", "http://127.0.0.1:5174"]
    # Upload storage: local disk by default. Set all three to use Cloudinary
    # (free tier) in production — required on multi-host/ephemeral disks.
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    cloudinary_folder: str = "gramshiksha"

    @property
    def cloudinary_enabled(self) -> bool:
        return bool(self.cloudinary_cloud_name and self.cloudinary_api_key
                    and self.cloudinary_api_secret)
    # Error tracking (Sentry free tier). Empty = disabled (dev default).
    sentry_dsn: str = ""
    sentry_env: str = "production"

    # --- Deploy safety gates -------------------------------------------
    # Explicit environment marker. Empty = infer from DATABASE_URL (historic
    # behaviour). Set APP_ENV=production on hosts where a *forgotten*
    # DATABASE_URL must not silently demote the app to dev mode: the URL is
    # itself the production signal, so the signal is absent exactly when the
    # mistake happens (ephemeral SQLite, demo accounts, logged reset codes).
    app_env: str = ""
    # Demo accounts (admin@gramshiksha.in / Admin@1234, etc.) are a dev
    # convenience. "auto" seeds them ONLY on a local SQLite DB; production
    # (Postgres) never gets them unless you explicitly force "true".
    # Values: auto | true | false
    seed_demo: str = "auto"
    # Ephemeral disks (Render free tier) destroy backend/uploads/ on every
    # redeploy. Production must use Cloudinary; set this ONLY if you mounted
    # a real persistent disk at backend/uploads.
    allow_ephemeral_uploads: bool = False
    # API reference (/docs + /openapi.json) is a map of the attack surface.
    # None = auto: on in dev, off in production. ENABLE_DOCS=true to expose it
    # deliberately; false to hide it locally too.
    docs_enabled: Optional[bool] = None

    # --- Password reset delivery (SMTP) --------------------------------
    # Empty host = not configured → codes are never sent (see mailer.py).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "no-reply@gramshiksha.in"
    smtp_use_tls: bool = True  # STARTTLS; false for implicit-TLS port 465

    @property
    def is_production(self) -> bool:
        """APP_ENV=production forces production; otherwise a non-SQLite
        DATABASE_URL is the production signal (the proxy main.py's guards
        already use).

        Deliberately one-way: only the value "production" can escalate, and
        nothing can de-escalate a Postgres URL back to dev — otherwise a typo
        like APP_ENV=deveopment on a real instance would switch every guard
        off. The point is that forgetting DATABASE_URL no longer means
        "development", because APP_ENV already said production.
        """
        if self.app_env.strip().lower() in ("production", "prod"):
            return True
        return not self.database_url.startswith("sqlite")

    @property
    def seed_demo_enabled(self) -> bool:
        flag = self.seed_demo.strip().lower()
        if flag in ("1", "true", "yes", "on"):
            return True
        if flag in ("0", "false", "no", "off"):
            return False
        return not self.is_production  # auto

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_host)

    @property
    def docs_on(self) -> bool:
        return (not self.is_production) if self.docs_enabled is None else self.docs_enabled


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
