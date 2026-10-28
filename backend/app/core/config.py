from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BACKEND_DIR / ".env"), extra="ignore")

    ENVIRONMENT: str = "development"
    SECRET_KEY: str = "dev-only-insecure-secret-key-change-me-please-0123456789"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    DATABASE_URL: str = f"sqlite:///{(BACKEND_DIR / 'inspection.db').as_posix()}"
    STORAGE_DIR: str = str(BACKEND_DIR / "storage")
    MODELS_DIR: str = str(BACKEND_DIR.parent / "models")
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    MAX_UPLOAD_MB: int = 15
    BATCH_WORKERS: int = 2
    BATCH_QUEUE_SIZE: int = 500
    BATCH_INLINE: bool = False  # process batch jobs synchronously (used by tests)
    MAX_IMAGE_SIDE: int = 640
    ADMIN_EMAIL: str = "admin@example.com"
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = ""

    @field_validator("SECRET_KEY")
    @classmethod
    def _secret(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def storage_path(self) -> Path:
        p = Path(self.STORAGE_DIR)
        if not p.is_absolute():
            p = BACKEND_DIR / p
        p.mkdir(parents=True, exist_ok=True)
        return p.resolve()

    @property
    def models_path(self) -> Path:
        p = Path(self.MODELS_DIR)
        if not p.is_absolute():
            p = BACKEND_DIR / p
        return p.resolve()

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.is_production and s.SECRET_KEY.startswith("dev-only"):
        raise RuntimeError("Refusing to start in production with the default SECRET_KEY")
    return s
