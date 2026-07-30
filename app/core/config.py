"""应用配置。"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置，从环境变量读取。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # 应用
    APP_NAME: str = "OCAP System"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = Field(default=False)
    API_V1_PREFIX: str = "/api/v1"
    DEFAULT_LOCALE: str = "zh-CN"

    # 数据库驱动：postgres | sqlite
    DB_DRIVER: str = "postgres"
    SQLITE_PATH: str = "ocap.db"

    # PostgreSQL
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "ocap"
    POSTGRES_PASSWORD: str = "ocap"
    POSTGRES_DB: str = "ocap"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # JWT
    JWT_SECRET: str = "ocap-dev-secret-change-me-please-use-32+bytes"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # 打底数据
    SEED_DATA_DIR: str = "app/db/seed/data"
    SEED_ON_STARTUP: bool = False

    # 集成模式
    INTEGRATION_DEFAULT_MODE: str = "mock"

    @property
    def async_database_url(self) -> str:
        """异步数据库 URL（按驱动分支）。"""
        if self.DB_DRIVER == "sqlite":
            if self.SQLITE_PATH == ":memory:":
                return "sqlite+aiosqlite:///:memory:"
            return f"sqlite+aiosqlite:///{self.SQLITE_PATH}"
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def sync_database_url(self) -> str:
        """同步数据库 URL（Alembic 用）。"""
        if self.DB_DRIVER == "sqlite":
            if self.SQLITE_PATH == ":memory:":
                return "sqlite:///:memory:"
            return f"sqlite:///{self.SQLITE_PATH}"
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def redis_url(self) -> str:
        """Redis URL。"""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


@lru_cache
def get_settings() -> Settings:
    """获取配置单例。"""
    return Settings()


settings = get_settings()
