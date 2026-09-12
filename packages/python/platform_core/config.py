from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://platform:platform@localhost:5432/platform"
    redis_url: str = "redis://localhost:6379/0"
    object_storage_endpoint: str = "http://localhost:9000"
    object_storage_bucket: str = "platform-files"
    object_storage_access_key: str = "test"
    object_storage_secret_key: str = "test"
    object_storage_region: str = "us-east-1"
    file_retention_days: int = 30
    max_upload_bytes: int = 20 * 1024 * 1024
    telegram_bot_token: str = ""
    telegram_orders_enabled: bool = False
    admin_cookie_secure: bool = True
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
