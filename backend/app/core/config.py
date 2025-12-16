from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:4321"

    database_url: str = "postgresql+asyncpg://ladatajusta:ladatajusta@localhost:5432/ladatajusta"

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    user_agent: str = "LaDataJustaBot/0.1"

    # JWT settings
    jwt_secret: str = "change-this-secret-in-production-use-openssl-rand-hex-32"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
