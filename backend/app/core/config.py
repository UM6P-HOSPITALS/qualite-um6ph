from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Base de données
    database_url: str = "postgresql+psycopg://qualite-um6ph:qualite-um6ph@localhost:5432/qualite-um6ph"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Authentification classique (JWT maison, en attendant Microsoft Entra ID)
    jwt_secret_key: str = "change-moi-en-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480  # 8h

    # Microsoft Entra ID (à remplir au ticket FEATURE-SETUP-03)
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""

    # SMTP (à remplir au ticket FEATURE-SETUP-05)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
