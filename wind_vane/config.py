from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/wind_vane"
    smtp_password: str = ""
    notifier_enabled: bool = True
    notifier_email_to: str = ""
    notifier_email_from: str = "wind-vane-notifier@localhost"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_use_tls: bool = True


settings = Settings()
