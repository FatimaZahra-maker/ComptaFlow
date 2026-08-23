from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "ComptaFlow API"
    APP_ENV: str = "development"
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
    # --- Groq : fournisseur cloud PRIORITAIRE du pipeline ---
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_TIMEOUT_SECONDS: int = 15
    CORS_ORIGINS: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174"
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    # Les anciennes variables devenues inutilisées sont ignorées afin de ne pas
    # casser un environnement existant. Elles ne sont ni lues par le pipeline,
    # ni exposées par l'API.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
