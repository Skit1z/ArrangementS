"""应用配置：全部通过环境变量注入，敏感项不落盘。"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    app_secret: str = Field(default="dev-app-secret-change-me", alias="APP_SECRET")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    database_url: str = Field(
        default="postgresql+psycopg://scheduler:scheduler@localhost:5432/scheduler",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    jwt_secret: str = Field(default="dev-jwt-secret-change-me", alias="JWT_SECRET")
    csrf_secret: str = Field(default="dev-csrf-secret-change-me", alias="CSRF_SECRET")
    # AES-256-GCM 字段级加密密钥：base64(32 字节)。为空时启动即报错（生产必须提供）。
    field_encryption_key: str = Field(default="", alias="FIELD_ENCRYPTION_KEY")

    access_token_ttl_minutes: int = Field(default=240, alias="ACCESS_TOKEN_TTL_MINUTES")
    refresh_token_ttl_days: int = Field(default=14, alias="REFRESH_TOKEN_TTL_DAYS")

    file_storage_path: str = Field(default="./var/files", alias="FILE_STORAGE_PATH")
    public_base_url: str = Field(default="http://localhost:8000", alias="PUBLIC_BASE_URL")
    max_upload_mb: int = Field(default=20, alias="MAX_UPLOAD_MB")

    cookie_secure: bool = Field(default=False, alias="COOKIE_SECURE")
    cookie_domain: str | None = Field(default=None, alias="COOKIE_DOMAIN")
    cors_origins: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")

    login_max_failures: int = Field(default=5, alias="LOGIN_MAX_FAILURES")
    login_lock_seconds: int = Field(default=300, alias="LOGIN_LOCK_SECONDS")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
