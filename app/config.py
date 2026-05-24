from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: str = ""
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/battleship"
    )
    host: str = "0.0.0.0"
    port: int = 8000
    dev_mode: bool = False
    super_admin_token: str = ""

    @property
    def database_url_sync(self) -> str:
        return self.database_url.replace("+asyncpg", "")


settings = Settings()
