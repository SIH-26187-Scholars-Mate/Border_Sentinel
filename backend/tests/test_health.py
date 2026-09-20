"""
tests/test_health.py
Health check endpoint tests.
"""


def test_health_returns_200(client):
    r = client.get("/health")
    assert r.status_code == 200


def test_health_returns_ok_json(client):
    r = client.get("/health")
    assert r.json() == {"status": "ok"}


def test_health_content_type_json(client):
    r = client.get("/health")
    assert "application/json" in r.headers["content-type"]
