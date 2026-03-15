from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "app_example"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    APP_SECRET_KEY: str = "change-me-in-production"
    JWT_SECRET_KEY: str = "change-me-jwt-secret"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ALGORITHM: str = "HS256"

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/app_example"

    DEFAULT_LOCALE: str = "en"
    SUPPORTED_LOCALES: list[str] = ["en", "es"]

    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "console"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
