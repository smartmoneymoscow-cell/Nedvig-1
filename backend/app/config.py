from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Realty Platform"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://realty:realty@localhost:5432/realty_db"

    # Elasticsearch
    ES_URL: str = "http://localhost:9200"
    ES_INDEX: str = "listings"

    # AI
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDING_DIM: int = 384

    # Scraping
    SCRAPE_CONCURRENT_REQUESTS: int = 8
    SCRAPE_DOWNLOAD_DELAY: float = 1.5

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
