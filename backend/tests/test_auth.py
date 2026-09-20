"""
tests/test_auth.py
Authentication endpoint tests.

Note: /auth/login is NOT tested against Supabase here — we only have
placeholder credentials.  We test the JWT path (decode + /auth/me)
which is fully self-contained.
"""


# ── /auth/me — unauthenticated ─────────────────────────────────────────────────

def test_me_no_token_is_401(client):
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_me_garbage_token_is_401(client):
    r = client.get("/auth/me", headers={"Authorization": "Bearer not.a.real.token"})
    assert r.status_code == 401
    assert "Invalid token" in r.json()["detail"]


def test_me_malformed_header_is_401(client):
    """Wrong scheme (Basic instead of Bearer) → 401 from HTTPBearer."""
    r = client.get("/auth/me", headers={"Authorization": "Basic abc123"})
    assert r.status_code == 401


# ── /auth/me — authenticated ──────────────────────────────────────────────────

def test_me_valid_token_returns_user(client, auth_headers):
    r = client.get("/auth/me", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == "test-uuid-1234"
    assert data["email"] == "dev@test.local"
    assert data["role"] == "authenticated"


def test_me_valid_token_shape(client, auth_headers):
    """Response must include id, email, role, full_name — no extras that leak internals."""
    r = client.get("/auth/me", headers=auth_headers)
    assert set(r.json().keys()) == {"id", "email", "role", "full_name"}


# ── PATCH /auth/me — update display name ──────────────────────────────────────

class _FakeAdminAuth:
    """Records the last update_user_by_id call instead of hitting Supabase."""

    def __init__(self):
        self.calls = []

    def update_user_by_id(self, user_id, attrs):
        self.calls.append((user_id, attrs))


class _FakeSupabaseClient:
    def __init__(self):
        self.auth = type("_A", (), {"admin": _FakeAdminAuth()})()


def test_update_me_sets_full_name(client, auth_headers, monkeypatch):
    fake_client = _FakeSupabaseClient()
    monkeypatch.setattr("app.api.routes.auth.get_supabase", lambda: fake_client)

    r = client.patch("/auth/me", json={"full_name": "Prakash Singh"}, headers=auth_headers)

    assert r.status_code == 200
    data = r.json()
    assert data["full_name"] == "Prakash Singh"
    assert data["id"] == "test-uuid-1234"
    # The service-role call must target the caller's own id from the verified
    # token, never a client-supplied one.
    assert fake_client.auth.admin.calls == [
        ("test-uuid-1234", {"user_metadata": {"full_name": "Prakash Singh"}})
    ]


def test_update_me_rejects_blank_name(client, auth_headers, monkeypatch):
    monkeypatch.setattr("app.api.routes.auth.get_supabase", lambda: _FakeSupabaseClient())
    r = client.patch("/auth/me", json={"full_name": "   "}, headers=auth_headers)
    assert r.status_code == 400


def test_update_me_requires_auth(client):
    r = client.patch("/auth/me", json={"full_name": "Someone"})
    assert r.status_code == 401


def test_update_me_surfaces_supabase_failure_as_502(client, auth_headers, monkeypatch):
    class _Boom:
        def update_user_by_id(self, *a, **k):
            raise RuntimeError("supabase unreachable")

    class _BoomClient:
        def __init__(self):
            self.auth = type("_A", (), {"admin": _Boom()})()

    monkeypatch.setattr("app.api.routes.auth.get_supabase", lambda: _BoomClient())
    r = client.patch("/auth/me", json={"full_name": "Prakash"}, headers=auth_headers)
    assert r.status_code == 502
