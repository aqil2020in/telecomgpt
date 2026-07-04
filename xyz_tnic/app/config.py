"""Environment configuration via pydantic-settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "XYZ Telecom Network Intelligence Copilot"
    app_env: str = "development"
    log_level: str = "INFO"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    database_url: str = "postgresql://tnic:tnic@localhost:5432/tnic"
    sqlite_fallback: bool = True

    chroma_persist_dir: str = "./data/chroma"
    rag_collection: str = "tnic_knowledge"

    enable_openai_reports: bool = True
    enable_chroma: bool = True

    data_dir: Path = Path(__file__).resolve().parent.parent / "data"

    @property
    def use_sqlite(self) -> bool:
        if self.app_env == "test":
            return True
        return self.sqlite_fallback and self.database_url.startswith("sqlite")

    @property
    def effective_database_url(self) -> str:
        if self.app_env == "test":
            return "sqlite:///./data/test_tnic.db"
        if self.use_sqlite and not self.database_url.startswith("sqlite"):
            return "sqlite:///./data/tnic_local.db"
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
