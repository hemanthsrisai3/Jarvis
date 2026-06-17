import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Base workspace directory (for file operations tool sandbox)
    WORKSPACE_DIR: Path = Path(os.environ.get("USERPROFILE", "C:/Users/Hemanth")) / "SecureJarvisBotWorkspace"

    # Ollama settings
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "llama3"
    EMBEDDING_MODEL: str = "nomic-embed-text"

    # Database settings
    DATA_DIR: Path = Path("d:/Code/SecureJarvisBot/data")
    DATABASE_PATH: Path = Path("d:/Code/SecureJarvisBot/data/jarvis.db")
    VECTOR_DB_PATH: Path = Path("d:/Code/SecureJarvisBot/data/vectors.json")

    # API configuration
    API_PORT: int = 8000
    API_HOST: str = "0.0.0.0"

    # System Monitor Settings
    GPU_MONITOR_ENABLED: bool = True

    # Weather settings
    WEATHER_API_URL: str = "https://api.open-meteo.com/v1/forecast"

# Initialize settings
settings = Settings()

# Ensure critical directories exist
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
