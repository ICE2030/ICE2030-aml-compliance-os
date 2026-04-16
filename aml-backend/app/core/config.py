import os
from pydantic_settings import BaseSettings
from typing import Optional

_default_db = "sqlite+aiosqlite:////data/app.db" if os.path.isdir("/data") else "sqlite+aiosqlite:///./aml_compliance.db"


class Settings(BaseSettings):
    APP_NAME: str = "AML Compliance OS"
    APP_VERSION: str = "1.0.0"
    DATABASE_URL: str = _default_db
    SECRET_KEY: str = "aml-compliance-os-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    DEFAULT_ADMIN_EMAIL: str = "admin@aml-os.sa"
    DEFAULT_ADMIN_PASSWORD: str = "admin123"

    class Config:
        env_file = ".env"


settings = Settings()
