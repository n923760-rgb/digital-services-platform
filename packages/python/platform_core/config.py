from functools import lru_cache

from pydantic import Field
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
    max_user_upload_bytes: int = 100 * 1024 * 1024
    pdf_sandbox_root: str = ""
    backup_status_path: str = ""
    telegram_bot_token: str = ""
    telegram_orders_enabled: bool = False
    service_activation_enabled: bool = False
    admin_cookie_secure: bool = True
    admin_login_source_limit: int = Field(default=30, ge=1, le=1000)
    admin_login_account_limit: int = Field(default=10, ge=1, le=1000)
    admin_login_pair_limit: int = Field(default=5, ge=1, le=1000)
    admin_login_window_seconds: int = Field(default=900, ge=60, le=86400)
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
