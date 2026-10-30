import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    sandbox_backend: str = os.getenv("SANDBOX_BACKEND", "docker")
    sandbox_image: str = os.getenv("SANDBOX_IMAGE", "python:3.11-slim")
    sandbox_timeout: int = int(os.getenv("SANDBOX_TIMEOUT", "20"))
    inference_base_url: str = os.getenv(
        "VULTR_INFERENCE_BASE_URL", "https://api.vultrinference.com/v1"
    )
    inference_api_key: str = os.getenv("VULTR_INFERENCE_API_KEY", "")
    inference_model: str = os.getenv("VULTR_INFERENCE_MODEL", "llama-3.3-70b-instruct-fp8")
    db_path: str = os.getenv("DB_PATH", "data/ledgerlock.db")
    sandbox_work_root: str = os.getenv("SANDBOX_WORK_ROOT", "")
    app_root: str = os.getenv("APP_ROOT", "")


settings = Settings()
