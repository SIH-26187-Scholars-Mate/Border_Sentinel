"""
ai/utils/config.py
Settings for the AI module, loaded from a .env file at the ai/ root
(mirrors the pattern used in backend/app/core/config.py).
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    backend_url: str = "http://localhost:8000"
    # Must exactly match backend's dedicated AI_SERVICE_KEY.
    service_key: str = ""
    camera_source: str = "0"  # webcam index as a string, or a video file path
    confidence_threshold: float = 0.5
    # Optional JSON-encoded polygon for the intrusion zone, e.g.
    # "[[100,100],[400,100],[400,400],[100,400]]". Left empty = no zone set.
    fence_zone: str = ""
    preview_host: str = "0.0.0.0"
    preview_port: int = 8001
    # Software low-light enhancement ("night vision"). Only frames darker
    # than night_vision_brightness_threshold (0-255 grayscale mean) get
    # touched; normal daylight footage passes through unchanged.
    night_vision_enabled: bool = True
    night_vision_brightness_threshold: float = 90.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
