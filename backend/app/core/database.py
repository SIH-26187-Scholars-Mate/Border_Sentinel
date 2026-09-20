"""Shared Supabase database client.

The Supabase dependency is imported lazily so the isolated unit-test mode can
run without opening a database connection. Production always uses the service
role key through this trusted backend client.
"""
from functools import lru_cache
from typing import Any

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_supabase() -> Any:
    from supabase import create_client

    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)
