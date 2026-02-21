from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/solar_system_db"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    GENERATED_DIR: str = "generated"

    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    ASSETS_DIR: Path = Path(__file__).resolve().parent.parent / "assets"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
