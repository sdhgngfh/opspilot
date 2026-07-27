from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.api as api_module
from app.api import app, get_audit_store, get_settings, get_user_store
from app.audit import SQLiteAuditStore, build_audit_store, new_audit_event
from app.config import Settings
from app.persistence import build_checkpointer, build_ticket_store, build_user_store
from app.rate_limit import (
    InMemoryRateLimiter,
    RateLimitDecision,
    build_rate_limiter,
)
from app.security import OIDCTokenVerifier, UserStore
from app.tools import TicketStore


def test_oidc_requires_complete_asymmetric_configuration() -> None:
    with pytest.raises(ValueError, match="OIDC_ISSUER"):
        Settings(auth_enabled=True, auth_provider="oidc")

    with pytest.raises(ValueError, match="非对称"):
        Settings(
            auth_enabled=True,
            auth_provider="oidc",
            oidc_issuer="https://id.example.com",
            oidc_audience="opspilot",
            oidc_jwks_url="https://id.example.com/.well-known/jwks.json",
            oidc_algorithms=["HS256"],
        )


def test_otel_requires_http_exporter_endpoint() -> None:
    with pytest.raises(ValueError, match="OTEL_EXPORTER_OTLP_ENDPOINT"):
        Settings(
            otel_tracing_enabled=True,
            otel_exporter_otlp_endpoint="collector:4318/v1/traces",
        )


def test_oidc_subject_maps_to_live_local_authorization(
    settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secure = settings.model_copy(
        update={
            "auth_enabled": True,
            "auth_provider": "oidc",
            "oidc_issuer": "https://id.example.com",
            "oidc_audience": "opspilot",
            "oidc_jwks_url": "https://id.example.com/.well-known/jwks.json",
        }
    )
    store = UserStore(tmp_path / "oidc-users.sqlite")
    identity = store.create_user(
        username="oidc-user",
        password="unused-password",
        roles=["support"],
        departments=["it"],
        scopes=["knowledge:read"],
        external_subject="https://id.example.com|employee-42",
    )

    class FakeVerifier:
        @staticmethod
        def subject(token: str) -> str:
            assert token == "enterprise-token"
            return "https://id.example.com|employee-42"

    monkeypatch.setattr(api_module, "_oidc_verifier", lambda *args: FakeVerifier())
    app.dependency_overrides[get_settings] = lambda: secure
    app.dependency_overrides[get_user_store] = lambda: store
    client = TestClient(app)
    try:
        response = client.get(
            "/v1/auth/me",
            headers={"Authorization": "Bearer enterprise-token"},
        )
        password_login = client.post(
            "/v1/auth/token",
            data={"username": "oidc-user", "password": "unused-password"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["user_id"] == identity.user_id
    assert response.json()["roles"] == ["support"]
    assert password_login.status_code == 404


def test_oidc_verifier_enforces_configured_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verifier = OIDCTokenVerifier(
        issuer="https://id.example.com",
        audience="opspilot",
        jwks_url="https://id.example.com/jwks",
        algorithms=("RS256",),
    )

    class SigningKey:
        key = "public-key"

    class FakeJWKClient:
        @staticmethod
        def get_signing_key_from_jwt(token: str) -> SigningKey:
            assert token == "signed-token"
            return SigningKey()

    def fake_decode(token, key, **kwargs):
        assert token == "signed-token"
        assert key == "public-key"
        assert kwargs["issuer"] == "https://id.example.com"
        assert kwargs["audience"] == "opspilot"
        assert kwargs["algorithms"] == ("RS256",)
        assert set(kwargs["options"]["require"]) == {"sub", "iss", "aud", "iat", "exp"}
        return {"iss": "https://id.example.com", "sub": "employee-42"}

    verifier.jwk_client = FakeJWKClient()
    monkeypatch.setattr("app.security.jwt.decode", fake_decode)

    assert (
        verifier.subject("signed-token")
        == "https://id.example.com|employee-42"
    )


def test_local_persistence_factories_remain_offline(
    settings: Settings,
    tmp_path: Path,
) -> None:
    local = settings.model_copy(
        update={
            "auth_store_path": tmp_path / "users.sqlite",
            "ticket_store_path": tmp_path / "tickets.sqlite",
            "audit_store_path": tmp_path / "audit.sqlite",
        }
    )

    users = build_user_store(local)
    tickets = build_ticket_store(local)
    audit = build_audit_store(local)
    limiter = build_rate_limiter(local)
    _, resource = build_checkpointer(
        local,
        local_path=tmp_path / "factory-checkpoints.sqlite",
    )

    assert isinstance(users, UserStore)
    assert isinstance(tickets, TicketStore)
    assert isinstance(audit, SQLiteAuditStore)
    assert isinstance(limiter, InMemoryRateLimiter)
    resource.close()


def test_sqlite_audit_store_retention(tmp_path: Path) -> None:
    store = SQLiteAuditStore(tmp_path / "audit.sqlite")
    older = new_audit_event(
        request_id="old",
        actor_id=None,
        actor_username=None,
        method="GET",
        path="/old",
        status_code=200,
        latency_ms=1.0,
    ).model_copy(update={"occurred_at": datetime.now(UTC) - timedelta(days=10)})
    recent = new_audit_event(
        request_id="new",
        actor_id="user-1",
        actor_username="alice",
        method="POST",
        path="/v1/graph/ask",
        status_code=403,
        latency_ms=2.0,
    )
    store.record(older)
    store.record(recent)

    events = store.list_recent()
    deleted = store.purge_before(datetime.now(UTC) - timedelta(days=1))

    assert [event.request_id for event in events] == ["new", "old"]
    assert events[0].outcome == "denied"
    assert deleted == 1
    assert [event.request_id for event in store.list_recent()] == ["new"]


def test_in_memory_rate_limiter_enforces_fixed_window() -> None:
    limiter = InMemoryRateLimiter(limit=2, window_seconds=60)

    first = limiter.check("client")
    second = limiter.check("client")
    third = limiter.check("client")

    assert first.allowed is True
    assert second.allowed is True
    assert third.allowed is False
    assert third.remaining == 0
    assert 1 <= third.retry_after <= 60


def test_rate_limit_middleware_returns_standard_headers(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    limited = settings.model_copy(update={"rate_limit_enabled": True})

    class DenyLimiter:
        @staticmethod
        def check(key: str) -> RateLimitDecision:
            assert len(key) == 64
            return RateLimitDecision(
                allowed=False,
                limit=10,
                remaining=0,
                retry_after=17,
            )

    monkeypatch.setattr(api_module, "get_settings", lambda: limited)
    monkeypatch.setattr(api_module, "get_rate_limiter", lambda: DenyLimiter())
    response = TestClient(app).get("/health")

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "17"
    assert response.headers["X-RateLimit-Limit"] == "10"
    assert response.headers["X-Request-ID"]


def test_audit_middleware_records_authenticated_actor(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audited = settings.model_copy(update={"audit_enabled": True})

    class MemoryAuditStore:
        def __init__(self) -> None:
            self.events = []

        def record(self, event) -> None:
            self.events.append(event)

        def list_recent(self, *, limit: int = 100):
            return list(reversed(self.events[-limit:]))

    store = MemoryAuditStore()
    monkeypatch.setattr(api_module, "get_settings", lambda: audited)
    monkeypatch.setattr(api_module, "get_audit_store", lambda: store)
    app.dependency_overrides[get_audit_store] = lambda: store
    try:
        response = TestClient(app).get(
            "/v1/auth/me",
            headers={"X-Request-ID": "audit-test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "audit-test"
    assert store.events[-1].actor_id == "system"
    assert store.events[-1].path == "/v1/auth/me"
