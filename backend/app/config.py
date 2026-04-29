from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    NVIDIA_API_KEY: Optional[str] = None
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    DEFAULT_MODEL: str = "meta/llama-3.3-70b-instruct"
    FAST_MODEL: str = "openai/gpt-oss-20b"
    REASONING_MODEL: str = "qwen/qwen3-next-80b-a3b-instruct"
    MAX_RETRIES: int = 3
    MAX_CHARS: int = 180

    class Config:
        env_file = ".env"

settings = Settings()
