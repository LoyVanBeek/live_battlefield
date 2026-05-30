from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: str = ""
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/battleship"
    )
    host: str = "0.0.0.0"
    port: int = 8000
    dev_mode: bool = False
    admin_token: str = Field(default="", validation_alias="ADMIN_TOKEN")

    @property
    def database_url_sync(self) -> str:
        return self.database_url.replace("+asyncpg", "")


settings = Settings()
