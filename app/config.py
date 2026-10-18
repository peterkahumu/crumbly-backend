from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        extra="ignore",
    )

    database_url: str
    jwt_secret: str

    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7

    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    cors_origins: str = ""
    currency: str = "KES"

    # Frontend URL (used for password reset and admin invitation links)
    frontend_url: str = "http://localhost:3000"

    # SMTP Email Configuration
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "Crumbly Marketplace"
    smtp_tls: bool = True
    smtp_ssl: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()