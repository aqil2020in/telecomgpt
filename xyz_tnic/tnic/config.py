"""Environment configuration for standalone XYZ TNIC."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "XYZ Telecom Network Intelligence Copilot"
    app_env: str = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    database_url: str = ""
    sqlite_fallback: bool = True

    rag_collection: str = "tnic_knowledge"
    enable_openai_reports: bool = True

    data_dir: Path = Path(__file__).resolve().parent.parent / "data"

    @property
    def chroma_persist_dir(self) -> str:
        return str(self.data_dir / "chroma")

    @property
    def enable_chroma(self) -> bool:
        return os.environ.get("TNIC_ENABLE_CHROMA", "1") == "1"

    @property
    def effective_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        if self.app_env == "test":
            return f"sqlite:///{self.data_dir / 'test_tnic.db'}"
        return f"sqlite:///{self.data_dir / 'tnic_local.db'}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
