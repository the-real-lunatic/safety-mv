from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "local")
    api_base_url: str = os.getenv("API_BASE_URL", "http://localhost:8000")

    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_api_base_url: str = os.getenv("OPENAI_API_BASE_URL", "https://api.openai.com/v1")
    openai_healthcheck_model: str | None = os.getenv("OPENAI_HEALTHCHECK_MODEL")
    openai_text_model: str | None = os.getenv("OPENAI_TEXT_MODEL")
    sora_api_key: str | None = os.getenv("SORA_API_KEY")
    sora_api_base_url: str = os.getenv("SORA_API_BASE_URL", "https://api.openai.com/v1")
    sora_model: str | None = os.getenv("SORA_MODEL")
    sora_slot_seconds: int = int(os.getenv("SORA_SLOT_SECONDS", "12"))
    sora_enabled: bool = os.getenv("SORA_ENABLED", "true").lower() == "true"
    suno_api_key: str | None = os.getenv("SUNO_API_KEY")
    suno_api_base_url: str = os.getenv("SUNO_API_BASE_URL", "https://api.sunoapi.org")
    suno_model: str = os.getenv("SUNO_MODEL", "V4_5ALL")
    pipeline_mode: str = os.getenv("PIPELINE_MODE", "mock")

    minio_endpoint: str = os.getenv("MINIO_ENDPOINT", "minio:9000")
    minio_access_key: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    minio_secret_key: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    minio_secure: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"
    minio_bucket: str = os.getenv("MINIO_BUCKET", "safetymv-artifacts")
    minio_enabled: bool = os.getenv("MINIO_ENABLED", "true").lower() == "true"

    redis_url: str | None = os.getenv("REDIS_URL")
    strategy_dir: str = os.getenv("STRATEGY_DIR", "strategies")


settings = Settings()
