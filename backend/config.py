"""
Central configuration for Saathi.

Everything here is read from environment variables (see .env.example).
No credential ever has a hardcoded fallback value containing a real
secret — only safe, non-secret defaults for local development.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # --- Rime (voice generation) ---
    RIME_API_KEY: str = os.getenv("RIME_API_KEY", "")
    RIME_MODEL_ID: str = os.getenv("RIME_MODEL_ID", "coda")
    # Companion persona: "Lyra" — confirmed real Coda English voice
    # (checked against Rime's live catalog on 2026-08-09).
    RIME_DEFAULT_SPEAKER: str = os.getenv("RIME_DEFAULT_SPEAKER", "lyra")
    # Companion persona: "Nadi" — confirmed real Hindi-capable Coda
    # voice (same catalog check). Alternative confirmed option: "taru".
    RIME_HINDI_SPEAKER: str = os.getenv("RIME_HINDI_SPEAKER", "nadi")
    RIME_TTS_URL: str = os.getenv("RIME_TTS_URL", "https://users.rime.ai/v1/rime-tts")
    RIME_TIMEOUT_SECONDS: float = float(os.getenv("RIME_TIMEOUT_SECONDS", "12"))

    # --- Qdrant (memory / retrieval) ---
    # QDRANT_MODE = "local" (embedded, on-disk, no account needed) or "cloud"
    QDRANT_MODE: str = os.getenv("QDRANT_MODE", "local")
    QDRANT_LOCAL_PATH: str = os.getenv("QDRANT_LOCAL_PATH", "./qdrant_data")
    QDRANT_URL: str = os.getenv("QDRANT_URL", "")
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "patient_memory")
    QDRANT_VECTOR_SIZE: int = int(os.getenv("QDRANT_VECTOR_SIZE", "64"))

    # --- Product logic ---
    # Number of *consecutive* missed doses before a caregiver alert fires.
    ESCALATION_THRESHOLD: int = int(os.getenv("ESCALATION_THRESHOLD", "2"))
    MAX_CLARIFYING_REASKS: int = int(os.getenv("MAX_CLARIFYING_REASKS", "2"))

    # --- Vision (prescription photo parsing) ---
    # Optional. Without this key, prescription photo upload still works
    # as a UI flow — the photo is shown and every field is simply typed
    # in manually instead of auto-filled. See backend/vision_client.py.
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_VISION_MODEL: str = os.getenv("ANTHROPIC_VISION_MODEL", "claude-sonnet-4-6")

    # --- Patient registry (caregiver-added/edited patients) ---
    PATIENT_STORE_PATH: str = os.getenv("PATIENT_STORE_PATH") or os.path.join(
        os.path.dirname(__file__), "data", "patients_store.json"
    )

    # --- Server ---
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))


settings = Settings()
