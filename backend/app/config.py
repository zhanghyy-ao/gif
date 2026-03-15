import os
from pydantic import BaseSettings

class Settings(BaseSettings):
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "outputs")

settings = Settings()

def check_env():
    if not settings.DASHSCOPE_API_KEY:
        raise RuntimeError("DASHSCOPE_API_KEY is not set. Please export it or provide .env file.")
