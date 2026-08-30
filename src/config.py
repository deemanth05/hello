from pathlib import Path
from pydantic_settings import BaseSettings,SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):

    DATABASE_PATH: Path = BASE_DIR/"dmart_store.db"

    STORE_NAME: str = "D mart Express"
    STORE_PHONE:str = "+917676219923"
    MINIMUM_ORDER_VALUE:float = 250.0
    DELIVERY_FEE:float = 30.0

    FREE_DELIVERY_THRESHOLD:float = 800.0

    OLLAMA_HOST:str = "http://localhost:11434"
    OLLAMA_MODEL:str = "qwen2.5:7b"

    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8765

    model_config = SettingsConfigDict(env_file=BASE_DIR/".env",extra="ignore")


settings = Settings()
