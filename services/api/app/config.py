from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    frontend_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"
    jwt_secret: str = "dev-secret"
    database_url: str = "sqlite:///./jobnova.db"

    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""

    openai_api_key: str = ""

    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    apply_worker_secret: str = ""

@lru_cache
def get_settings() -> Settings:
    return Settings()
