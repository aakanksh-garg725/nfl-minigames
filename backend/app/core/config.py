from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env", extra="ignore"
    )
    database_url: str = "sqlite:///./local.db"
    supabase_url: str = "https://hgzdvceooagfiqhkfzrj.supabase.co"
    supabase_publishable_key: str = ""
    app_env: str = "development"
    auth_mode: str = "supabase"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    admin_user_ids: str = ""
    fantasy_data_provider: str = "espn"
    espn_league_id: int = 0
    espn_swid: str = ""
    espn_s2: str = ""
    public_app_url: str = "http://localhost:3000"
    auto_sync: bool = False

    @property
    def demo(self) -> bool:
        return self.auth_mode == "demo"

    def validate_runtime(self):
        if self.demo and (
            self.app_env != "development" or not self.database_url.startswith("sqlite")
        ):
            raise ValueError("Demo identity is allowed only on a development SQLite database")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_runtime()
    return settings
