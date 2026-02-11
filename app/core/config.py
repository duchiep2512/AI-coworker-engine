"""
Core configuration — loads environment variables and exposes typed settings.
"""

from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application-wide settings loaded from .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL: str = "gemma-3-1b-it"
    GEMINI_TEMPERATURE: float = 0.3
    GEMINI_MAX_TOKENS: int = 1024

    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "coworker_engine"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres123"

    @property
    def postgres_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def postgres_sync_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB: str = "coworker_logs"

    FAISS_INDEX_DIR: str = "./data/faiss_indices"

    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    MAX_MESSAGE_LENGTH: int = 2000
    BLOCKED_TOPICS: str = "gambling,violence,adult_content"

    @property
    def blocked_topics_list(self) -> List[str]:
        return [t.strip() for t in self.BLOCKED_TOPICS.split(",") if t.strip()]

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parent.parent.parent

    @property
    def knowledge_dir(self) -> Path:
        return self.project_root / "app" / "knowledge" / "documents"

    @property
    def faiss_index_path(self) -> Path:
        return Path(self.FAISS_INDEX_DIR)

# Singleton — import this everywhere
settings = Settings()
