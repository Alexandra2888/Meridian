from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # LLM
    openai_api_key: str = Field(default="")
    model_planner: str = "gpt-4o-mini"
    model_agent: str = "gpt-4o-mini"
    model_synthesizer: str = "gpt-4o"
    # Dedicated model for the eval LLM-as-judge. Kept separate from `model_agent`
    # so a reviewer can swap the judge (e.g. to a stronger / different-family
    # model for less-biased grading) without disturbing the orchestrator.
    model_judge: str = "gpt-4o-mini"

    # CRM
    crm_provider: Literal["stub", "hubspot"] = "stub"
    hubspot_access_token: str = ""
    hubspot_timeout_seconds: float = 5.0

    # DB
    db_url: str = "sqlite+aiosqlite:///./data/meridian.db"

    # App
    log_level: str = "INFO"
    allowed_origins: str = "http://localhost:3000"

    # Observability
    langsmith_api_key: str = ""
    langsmith_project: str = "meridian"
    langchain_tracing_v2: bool = False

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
