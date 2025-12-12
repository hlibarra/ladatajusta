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

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
