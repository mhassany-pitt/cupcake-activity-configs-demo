import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

class Config:
    PORT: int = int(os.getenv("PORT", 8098))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

    # Ollama Cloud / API
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "https://api.ollama.ai").rstrip("/")
    OLLAMA_API_KEY: str = os.getenv("OLLAMA_API_KEY", "")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:latest")

config = Config()
