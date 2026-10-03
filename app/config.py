from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str  # postgresql+asyncpg://user:password@localhost:5432/moontales

    # ── Providers Selection ───────────────────────────────────────────────────
    TTS_PROVIDER: str = "gcp"              # "gcp" | "elevenlabs"
    LLM_PROVIDER: str = "gemini"           # "gemini" | "openai" | "groq"
    IMAGE_PROVIDER: str = "imagen"         # "imagen" | "dalle" | "replicate"

    # ── Google AI (Gemini 2.0 Flash + Imagen 3) ───────────────────────────────
    GOOGLE_AI_API_KEY: str = ""

    # ── GCP Cloud Text-to-Speech ──────────────────────────────────────────────
    GCP_TTS_VOICE_NAME: str = "en-US-Journey-F"
    GCP_TTS_LANGUAGE_CODE: str = "en-US"

    # ── ElevenLabs ────────────────────────────────────────────────────────────
    ELEVENLABS_API_KEY: str = ""
    DEFAULT_VOICE_ID: str = ""  # cloned voice ID

    # ── OpenAI ────────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    OPENAI_LLM_MODEL: str = "gpt-4o-mini"
    DALL_E_MODEL: str = "dall-e-3"

    # ── Groq ──────────────────────────────────────────────────────────────────
    GROQ_API_KEY: str = ""
    GROQ_LLM_MODEL: str = "llama-3.3-70b-versatile"

    # ── Replicate (Flux / SDXL) ───────────────────────────────────────────────
    REPLICATE_API_TOKEN: str = ""
    REPLICATE_MODEL: str = "black-forest-labs/flux-schnell"

    # ── Google Cloud Storage ──────────────────────────────────────────────────
    GCS_BUCKET_NAME: str
    GCS_PROJECT_ID: str

    # ── Firebase Auth ─────────────────────────────────────────────────────────
    # JSON string of the service account key downloaded from Firebase Console
    FIREBASE_SERVICE_ACCOUNT_JSON: str = ""

    # ── Google Cloud Credentials ──────────────────────────────────────────────
    GOOGLE_APPLICATION_CREDENTIALS: str = ""

    # ── App ───────────────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    DEFAULT_PAGE_COUNT: int = 5
    SIGNED_URL_EXPIRY_HOURS: int = 1

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()  # type: ignore[call-arg]
