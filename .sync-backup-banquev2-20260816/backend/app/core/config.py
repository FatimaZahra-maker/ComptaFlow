from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ---------------------------------------------------------
    # APPLICATION
    # ---------------------------------------------------------
    APP_NAME: str = "ComptaFlow API"
    APP_ENV: str = "development"
    DEBUG: bool = False

    # ---------------------------------------------------------
    # BASE DE DONNÉES / REDIS
    # ---------------------------------------------------------
    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6380/0"

    # ---------------------------------------------------------
    # SÉCURITÉ / JWT
    # ---------------------------------------------------------
    SECRET_KEY: str

    # 480 minutes = 8 heures
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # ---------------------------------------------------------
    # CORS
    # ---------------------------------------------------------
    # Dans .env :
    #
    # CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
    #
    CORS_ORIGINS: str = (
        "http://localhost:5173,"
        "http://127.0.0.1:5173,"
        "http://localhost:5174,"
        "http://127.0.0.1:5174"
    )

    # ---------------------------------------------------------
    # STOCKAGE / UPLOAD
    # ---------------------------------------------------------
    STORAGE_PATH: str = "./storage_local"

    MAX_UPLOAD_SIZE_MB: int = 20

    # ---------------------------------------------------------
    # OLLAMA
    # Fallback local seulement.
    # Il n'est plus préchargé au démarrage de Celery.
    # ---------------------------------------------------------
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:1b"

    # Ancienne variable conservée pour compatibilité
    # avec ton .env actuel.
    AI_PROVIDER: str = "local"

    # ---------------------------------------------------------
    # GROQ
    # Fournisseur cloud prioritaire
    # ---------------------------------------------------------
    GROQ_API_KEY: str = ""

    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    GROQ_TIMEOUT_SECONDS: int = 15

    # ---------------------------------------------------------
    # GEMINI
    # Conservé pour compatibilité / futurs fallbacks.
    # ---------------------------------------------------------
    GEMINI_API_KEY: str = ""

    GEMINI_MODEL: str = "gemini-2.5-flash-lite"

    GEMINI_TIMEOUT_SECONDS: int = 8

    # ---------------------------------------------------------
    # PYDANTIC SETTINGS
    # ---------------------------------------------------------
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",

        # Évite qu'une ancienne variable présente dans .env
        # fasse planter le backend.
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        """
        Convertit :

        http://localhost:5173,http://localhost:5174

        en :

        [
            "http://localhost:5173",
            "http://localhost:5174"
        ]
        """

        return [
            origin.strip()
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]


settings = Settings()