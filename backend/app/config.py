from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    NVIDIA_API_KEY: Optional[str] = None
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    FAST_MODEL: str = "openai/gpt-oss-120b"
    REASONING_MODEL: str = "qwen/qwen3-next-80b-a3b-instruct"
    MAX_RETRIES: int = 3
    MAX_CHARS: int = 180

    class Config:
        env_file = ".env"

settings = Settings()
