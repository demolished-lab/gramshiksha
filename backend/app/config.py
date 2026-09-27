from functools import lru_cache
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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
