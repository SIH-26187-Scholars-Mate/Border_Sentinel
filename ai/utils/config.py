"""
ai/utils/config.py
Settings for the AI module, loaded from a .env file at the ai/ root
(mirrors the pattern used in backend/app/core/config.py).
"""
import os
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
    # Expected direction of travel for counter-flow detection:
    # right | left | up | down | none (disable).
    flow_direction: str = "right"
    # Face recognition (see ai/face/face_recognizer.py).
    face_recognition: str = "on"          # "off" disables recognition
    face_match_threshold: float = 0.363   # cosine similarity for "same person"
    face_min_identify_px: int = 48        # faces narrower than this are not identified
    face_known_dir: str = ""              # empty = ai/face/known_faces

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def setting(name: str, default):
    """Read one setting from ai/.env or the environment, else `default`.

    Goes through Settings so values in the .env file are honoured (plain
    os.getenv would not see them); falls back to the raw environment so it
    also works where Settings is replaced by a stub (tests).
    """
    try:
        return getattr(get_settings(), name.lower())
    except Exception:
        return os.getenv(name.upper(), default)
