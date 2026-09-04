from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/clinic.db"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 12 * 60
    tool_api_key: str = "dev-tool-key"
    tool_hmac_secret: str = "dev-hmac-secret"
    exotel_webhook_token: str = "dev-exotel-token"
    seed_reception_email: str = "reception@adajan.clinic"
    seed_reception_password: str = "changeme"
    timezone: str = "Asia/Kolkata"
    cors_origins: str = "http://localhost:3000"
    hold_seconds: int = 90
    recording_retention_days: int = 90
    sarvam_api_key: str = ""
    sarvam_voice_api_key: str = ""
    exotel_account_sid: str = ""
    exotel_api_key: str = ""
    exotel_api_token: str = ""
    exotel_base_url: str = "https://api.in.exotel.com"


settings = Settings()
