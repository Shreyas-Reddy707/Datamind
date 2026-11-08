"""DataMind v2 Configuration Module.

Uses pydantic-settings for type-safe environment configuration with fail-fast
validation for production secrets and OWASP-compliant defaults.
"""

from __future__ import annotations

import os
from typing import Literal

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
os.environ["DISABLE_TELEMETRY"] = "TRUE"
os.environ["LITELLM_TELEMETRY"] = "False"

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Environment
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"  # noqa: S104
    PORT: int = 8000
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
        ]
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"
    DATABASE_SYNC_URL: str = "postgresql://postgres:postgres@localhost:5432/postgres"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security & Cryptography (Fail-fast validation)
    JWT_SECRET: str = Field(
        ..., min_length=32, description="At least 32-character high entropy key"
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    SESSION_SECRET: str = Field(..., min_length=32, description="Session encryption secret")
    LOCKOUT_MAX_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15

    # Local Ollama & LLM
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5-coder:7b"
    EMBEDDING_MODEL: str = "nomic-embed-text"
    OLLAMA_TIMEOUT: int = 120
    OLLAMA_MAX_RETRIES: int = 3

    # Storage Paths & Limits
    DATA_DIR: str = "data"
    UPLOADS_DIR: str = "data/uploads"
    MAX_FILE_SIZE_MB: int = 50
    MAX_ROWS: int = 500_000
    MAX_COLS: int = 500
    MAX_EXCEL_ROWS: int = 100_000
    MAX_HISTORY_MESSAGES: int = 500

    # ML & Statistical Thresholds (Preserved from v1)
    NULL_RATE_THRESHOLD: float = 0.3
    MIN_NUMERIC_FOR_CLUSTERING: int = 2
    MIN_NULL_RATE_FOR_ID: float = 0.9
    CORRELATION_MIN_NUMERIC: int = 3
    TRAIN_TEST_SPLIT_RATIO: float = 0.8
    CROSS_VALIDATION_FOLDS: int = 5
    FORECAST_HORIZON_DAYS: int = 30
    FORECAST_CONFIDENCE_LEVEL: float = 0.95

    @field_validator("JWT_SECRET", "SESSION_SECRET")
    @classmethod
    def validate_secrets_strength(cls, v: str) -> str:
        if len(v.strip()) < 32:
            raise ValueError(
                "Secret key must be at least 32 characters long to prevent brute-force attacks."
            )
        insecure_defaults = {
            "insecure-default-change-in-production",
            "your-random-secret-key-here",
            "changeme",
            "secret",
        }
        if v.strip().lower() in insecure_defaults:
            raise ValueError(
                "Insecure default secret key detected. You must set a unique, high-entropy secret."
            )
        return v

    @model_validator(mode="after")
    def validate_production_hardening(self) -> Settings:
        """Enforce strict production hardening checks."""
        if self.ENVIRONMENT == "production":
            if self.DEBUG:
                raise ValueError("DEBUG must be False in production environment.")
            for url_str, field_name in [
                (self.DATABASE_URL, "DATABASE_URL"),
                (self.DATABASE_SYNC_URL, "DATABASE_SYNC_URL"),
            ]:
                try:
                    parsed = make_url(url_str)
                    db_user = (parsed.username or "").lower()
                    db_pass = (parsed.password or "").lower()
                    if db_user == "postgres" and db_pass == "postgres":  # noqa: S105
                        raise ValueError(
                            f"Default postgres credentials are forbidden in production {field_name}."
                        )
                except ValueError:
                    raise
                except Exception as e:
                    raise ValueError(f"Invalid database URL in {field_name}: {e}") from e

            for origin in self.CORS_ORIGINS:
                if origin.strip() == "*" or "*" in origin:
                    raise ValueError("Wildcard '*' CORS origin is strictly forbidden in production.")
                if "localhost" in origin or "127.0.0.1" in origin:
                    raise ValueError(f"Localhost CORS origin '{origin}' is forbidden in production.")
        return self


settings = Settings()
