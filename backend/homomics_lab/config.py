from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HOMICS_")

    app_name: str = "HomomicsLab"
    port: int = 8080
    host: str = "0.0.0.0"
    debug: bool = False
    database_url: str = "sqlite+aiosqlite:///./homomics_lab.db"
    data_dir: Path = Path("./data")
    skills_dir: Path = Path("./skills")


settings = Settings()
