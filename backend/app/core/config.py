from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "ComptaFlow API"
    DATABASE_URL: str
    SECRET_KEY: str
    REDIS_URL: str
    OLLAMA_URL: str
    OLLAMA_MODEL: str
    STORAGE_PATH: str = "./storage_local"

    # --- Ancienne bascule, conservée pour compatibilité .env mais plus
    # utilisée pour router l'extraction (voir ai_service.extraire_donnees,
    # qui décide maintenant sur la seule présence de GROQ_API_KEY) ---
    AI_PROVIDER: str = "local"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash-lite"
    GEMINI_TIMEOUT_SECONDS: int = 8

    # --- Groq : fournisseur cloud PRIORITAIRE du pipeline ---
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_TIMEOUT_SECONDS: int = 15

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()