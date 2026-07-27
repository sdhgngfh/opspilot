from __future__ import annotations

from contextlib import contextmanager, nullcontext
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.audit import PostgresAuditStore, new_audit_event
from app.migrations import MigrationError, PostgresMigrator
from app.models import SubmitTicketToolInput, TicketDraft
from app.postgres_stores import PostgresTicketStore, PostgresUserStore
from app.rate_limit import PostgresRateLimiter
from app.security import hash_password


class _Result:
    def __init__(
        self,
        *,
        one: dict[str, Any] | None = None,
        rows: list[dict[str, Any]] | None = None,
        rowcount: int = 0,
    ) -> None:
        self.one = one
        self.rows = rows or []
        self.rowcount = rowcount

    def fetchone(self) -> dict[str, Any] | None:
        return self.one

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows


def _connector(connection: Any):
    @contextmanager
    def connect(database_url: str):
        assert database_url == "postgresql://test"
        yield connection

    return connect


class _UserConnection:
    def __init__(self) -> None:
        self.users: dict[str, dict[str, Any]] = {
            "alice": {
                "user_id": "user-1",
                "username": "alice",
                "password_hash": hash_password("correct-password", salt=b"\x02" * 16),
                "roles": ["support"],
                "departments": ["it"],
                "scopes": ["knowledge:read"],
                "external_subject": "https://id.example.com|alice",
            }
        }
        self.executed: list[tuple[str, object]] = []

    def execute(self, sql: str, params: object = None) -> _Result:
        self.executed.append((sql, params))
        normalized = " ".join(sql.split())
        if normalized.startswith("INSERT INTO app_users"):
            values = params
            assert isinstance(values, tuple)
            self.users[str(values[1])] = {
                "user_id": values[0],
                "username": values[1],
                "password_hash": values[2],
                "roles": values[3],
                "departments": values[4],
                "scopes": values[5],
                "external_subject": values[6],
            }
            return _Result()
        if "WHERE username = %s" in normalized:
            assert isinstance(params, tuple)
            return _Result(one=self.users.get(str(params[0])))
        if "WHERE user_id = %s" in normalized:
            assert isinstance(params, tuple)
            row = next(
                (item for item in self.users.values() if item["user_id"] == params[0]),
                None,
            )
            return _Result(one=row)
        if "WHERE external_subject = %s" in normalized:
            assert isinstance(params, tuple)
            row = next(
                (
                    item
                    for item in self.users.values()
                    if item["external_subject"] == params[0]
                ),
                None,
            )
            return _Result(one=row)
        return _Result()


def test_postgres_user_store_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _UserConnection()
    monkeypatch.setattr(
        "app.postgres_stores.connect_postgres",
        _connector(connection),
    )
    store = PostgresUserStore("postgresql://test")

    created = store.create_user(
        username="  BOB ",
        password="bob-password",
        roles=["support", "support"],
        departments=["it"],
        scopes=["knowledge:read"],
        external_subject="https://id.example.com|bob",
    )

    assert created.username == "bob"
    assert store.get_by_id(created.user_id) == created
    assert store.get_by_external_subject("https://id.example.com|bob") == created
    assert store.authenticate("alice", "correct-password") is not None
    assert store.authenticate("alice", "wrong-password") is None
    assert store.authenticate("missing", "wrong-password") is None
    with pytest.raises(ValueError, match="用户名不能为空"):
        store.create_user(
            username=" ",
            password="unused",
            roles=[],
            departments=[],
            scopes=[],
        )
    with pytest.raises(ValueError, match="未知权限范围"):
        store.create_user(
            username="eve",
            password="unused",
            roles=[],
            departments=[],
            scopes=["root:all"],
        )
    assert sum("CREATE TABLE" in sql for sql, _ in connection.executed) == 1


class _TicketConnection:
    def __init__(self) -> None:
        self.tickets: dict[str, dict[str, Any]] = {}

    def execute(self, sql: str, params: object = None) -> _Result:
        normalized = " ".join(sql.split())
        if normalized.startswith("INSERT INTO tickets"):
            values = params
            assert isinstance(values, tuple)
            workflow_id = str(values[1])
            row = self.tickets.setdefault(
                workflow_id,
                {
                    "ticket_id": values[0],
                    "workflow_id": workflow_id,
                    "requester": values[2],
                    "reviewer": values[3],
                    "review_action": values[4],
                    "draft": __import__("json").loads(str(values[5])),
                    "status": "submitted",
                    "created_at": values[6],
                },
            )
            return _Result(one=row)
        if "WHERE ticket_id = %s" in normalized:
            assert isinstance(params, tuple)
            row = next(
                (
                    item
                    for item in self.tickets.values()
                    if item["ticket_id"] == params[0]
                ),
                None,
            )
            return _Result(one=row)
        if "WHERE workflow_id = %s" in normalized:
            assert isinstance(params, tuple)
            return _Result(one=self.tickets.get(str(params[0])))
        if normalized.startswith("SELECT COUNT(*)"):
            return _Result(one={"count": len(self.tickets)})
        return _Result()


def test_postgres_ticket_store_returns_idempotent_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _TicketConnection()
    monkeypatch.setattr(
        "app.postgres_stores.connect_postgres",
        _connector(connection),
    )
    store = PostgresTicketStore("postgresql://test")
    payload = SubmitTicketToolInput(
        workflow_id="workflow-1",
        requester="alice",
        reviewer="lead",
        review_action="approve",
        draft=TicketDraft(
            title="修复订单权限",
            description="限制销售订单的跨部门访问。",
            category="access",
            priority="high",
            impact="可能发生越权访问",
            acceptance_criteria=["销售只能查看本部门订单"],
        ),
    )

    first = store.create(payload)
    second = store.create(payload)

    assert first == second
    assert store.get(first.ticket_id) == first
    assert store.get_by_workflow("workflow-1") == first
    assert store.get_by_workflow("missing") is None
    assert store.count() == 1


class _AuditConnection:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def execute(self, sql: str, params: object = None) -> _Result:
        normalized = " ".join(sql.split())
        if normalized.startswith("INSERT INTO audit_events"):
            values = params
            assert isinstance(values, tuple)
            self.rows.append(
                dict(
                    zip(
                        (
                            "audit_id",
                            "request_id",
                            "actor_id",
                            "actor_username",
                            "method",
                            "path",
                            "status_code",
                            "outcome",
                            "latency_ms",
                            "occurred_at",
                        ),
                        values,
                        strict=True,
                    )
                )
            )
        if normalized.startswith("SELECT * FROM audit_events"):
            assert isinstance(params, tuple)
            return _Result(rows=list(reversed(self.rows))[: int(params[0])])
        if normalized.startswith("DELETE FROM audit_events"):
            deleted = len(self.rows)
            self.rows.clear()
            return _Result(rowcount=deleted)
        return _Result()


def test_postgres_audit_store_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _AuditConnection()
    monkeypatch.setattr("app.audit.connect_postgres", _connector(connection))
    store = PostgresAuditStore("postgresql://test")
    event = new_audit_event(
        request_id="request-1",
        actor_id="user-1",
        actor_username="alice",
        method="POST",
        path="/v1/graph/ask",
        status_code=200,
        latency_ms=1.2345,
    )

    store.record(event)

    assert store.list_recent(limit=1) == [event]
    assert store.purge_before(datetime.now(UTC)) == 1


class _RateLimitConnection:
    def __init__(self) -> None:
        self.count = 0

    def execute(self, sql: str, params: object = None) -> _Result:
        if "RETURNING request_count" in sql:
            self.count += 1
            return _Result(one={"request_count": self.count})
        return _Result()


def test_postgres_rate_limiter_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _RateLimitConnection()
    monkeypatch.setattr("app.rate_limit.connect_postgres", _connector(connection))
    monkeypatch.setattr("app.rate_limit.time.time", lambda: 120.5)
    limiter = PostgresRateLimiter(
        "postgresql://test",
        limit=1,
        window_seconds=60,
    )

    first = limiter.check("client")
    second = limiter.check("client")

    assert first.allowed is True
    assert first.remaining == 0
    assert second.allowed is False
    assert second.retry_after == 59


class _MigrationConnection:
    def __init__(self) -> None:
        self.ledger_exists = False
        self.applied: dict[str, dict[str, Any]] = {}
        self.sql: list[str] = []

    def transaction(self):
        return nullcontext()

    def execute(self, sql: str, params: object = None) -> _Result:
        normalized = " ".join(sql.split())
        self.sql.append(normalized)
        if normalized.startswith("CREATE TABLE IF NOT EXISTS schema_migrations"):
            self.ledger_exists = True
        if normalized.startswith("SELECT to_regclass"):
            return _Result(
                one={"relation": "schema_migrations" if self.ledger_exists else None}
            )
        if normalized.startswith("SELECT version, name, checksum"):
            return _Result(rows=list(self.applied.values()))
        if normalized.startswith("INSERT INTO schema_migrations"):
            assert isinstance(params, tuple)
            version, name, checksum = params
            self.applied[str(version)] = {
                "version": version,
                "name": name,
                "checksum": checksum,
                "applied_at": datetime.now(UTC),
            }
        return _Result()


def test_postgres_migrator_apply_status_and_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = tmp_path / "001_create_example.sql"
    migration.write_text("CREATE TABLE example(id INTEGER);\n", encoding="utf-8")
    connection = _MigrationConnection()
    monkeypatch.setattr("app.migrations.connect_postgres", _connector(connection))
    migrator = PostgresMigrator("postgresql://test", tmp_path)

    applied = migrator.apply()
    repeated = migrator.apply()

    assert [item.status for item in applied] == ["applied"]
    assert [item.status for item in repeated] == ["applied"]
    assert sum("CREATE TABLE example" in sql for sql in connection.sql) == 1

    migration.write_text("CREATE TABLE example(id BIGINT);\n", encoding="utf-8")
    assert [item.status for item in migrator.status()] == ["drifted"]
    with pytest.raises(MigrationError, match="已被修改"):
        migrator.apply()
