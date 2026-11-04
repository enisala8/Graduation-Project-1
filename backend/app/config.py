from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Tüm ayarlar .env dosyasından (veya ortam değişkenlerinden) okunur."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "groq"  # groq | gemini
    llm_model: str = ""  # sağlayıcının konsolunda o gün listelenen model adı
    llm_api_key: str = ""

    mail_provider: str = "mock"  # mock | gmail

    database_url: str = "chronos.db"
    frontend_origin: str = "http://localhost:5173"


settings = Settings()
