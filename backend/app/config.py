from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    NVIDIA_API_KEY: str
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    DEFAULT_MODEL: str = "meta/llama-3.3-70b-instruct"
    MAX_RETRIES: int = 3
    MAX_CHARS: int = 180

    class Config:
        env_file = ".env"

settings = Settings()
