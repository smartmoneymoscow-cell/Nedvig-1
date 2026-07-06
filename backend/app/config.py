from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Realty Platform"
    DEBUG: bool = False

    # Database — defaults to SQLite for local dev, override with .env for PostgreSQL
    DATABASE_URL: str = "sqlite+aiosqlite:///./realty.db"

    # Elasticsearch (optional — empty string disables)
    ES_URL: str = ""
    ES_INDEX: str = "listings"

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    # Auth
    SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # AI
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDING_DIM: int = 384

    # Scraping
    SCRAPE_CONCURRENT_REQUESTS: int = 8
    SCRAPE_DOWNLOAD_DELAY: float = 1.5
    SCRAPE_PROXY_LIST: list[str] = []

    # Redis (optional — empty string disables)
    REDIS_URL: str = ""

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
