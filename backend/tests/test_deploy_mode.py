"""Hosted-deploy behaviour: ENABLE_AI_WORKERS=false must never spawn processes."""
from app.core.config import get_settings
from app.services.camera_worker import worker_manager


def test_workers_disabled_reports_disabled_and_spawns_nothing(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_ai_workers", False)

    started = worker_manager.start("11111111-1111-1111-1111-111111111111", 1, None)
    status = worker_manager.status("11111111-1111-1111-1111-111111111111", 1)

    assert started["running"] is False and started["status"] == "disabled"
    assert status["status"] == "disabled" and "ENABLE_AI_WORKERS" in status["ai_error"]
    assert worker_manager._processes == {}


def test_cors_regex_setting_defaults_empty():
    assert get_settings().cors_origin_regex == ""
