import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):

    DATABASE_PATH: Path = BASE_DIR/"dmart_store.db"

    STORE_NAME: str = "D mart Express"
    STORE_PHONE: str = "+17744930623"
    MINIMUM_ORDER_VALUE: float = 250.0
    DELIVERY_FEE:float = 30.0

    FREE_DELIVERY_THRESHOLD:float = 800.0

    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "gemma3:latest"
    LANGUAGE: str = "kn"  # Kannada (ಕನ್ನಡ)
    
    STT_MODEL_SIZE: str = "base"  # Multilingual Whisper
    STT_LANGUAGE: str = "kn"      # Kannada language detection / transcript

    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = int(os.getenv("PORT", "8765"))
    GEMINI_API_KEY: str = ""

    model_config = SettingsConfigDict(env_file=BASE_DIR/".env", extra="ignore")


settings = Settings()
