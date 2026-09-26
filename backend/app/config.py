from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """App settings loaded from the environment / repo-root `.env` (PLAN.md §3)."""

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mongodb_uri: str = ""
    mongodb_db: str = "mesh"
    jwt_secret: str = ""
    jwt_ttl_hours: int = 24
    google_client_id: str = ""
    cookie_secure: bool = False
    demo_login: bool = False
    coordinator_invite_code: str = ""
    nws_user_agent: str = "(Mesh, team-email@example.com)"
    muse_api_key: str = ""
    muse_base_url: str = "https://api.meta.ai/v1"
    muse_text_model: str = "muse-spark-1.3"
    muse_transcribe_model: str = "muse-voice-transcribe-1.0"
    llm_provider: Literal["mock", "muse"] = "mock"
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    elevenlabs_model_id: str = "eleven_multilingual_v2"
    hazard_cache_seconds: int = 300
    default_timezone: str = "America/New_York"
    realtime_mode: Literal["poll", "ws"] = "poll"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    vector_search: Literal["auto", "atlas", "local"] = "auto"


@lru_cache
def get_settings() -> Settings:
    return Settings()
