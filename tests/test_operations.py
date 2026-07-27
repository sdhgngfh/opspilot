from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from app.backup import (
    BackupError,
    DatabaseTarget,
    create_backup,
    manifest_path,
    restore_backup,
    verify_backup,
)
from app.config import Settings
from app.health import check_readiness
from app.migrations import MigrationError, load_migrations
from app.preflight import preflight_payload, run_preflight


def test_database_target_parses_credentials_without_exposing_them() -> None:
    target = DatabaseTarget.from_url(
        "postgresql://user%40example:p%40ss@db.internal:5544/opspilot?sslmode=require"
    )

    assert target.username == "user@example"
    assert target.password == "p@ss"
    assert target.database == "opspilot"
    assert target.environment()["PGPASSWORD"] == "p@ss"


def test_backup_manifest_and_restore_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[list[str]] = []

    def fake_run(command, **kwargs):
        commands.append(command)
        assert "secret" not in " ".join(command)
        if command[0] == "pg_dump":
            output = Path(command[command.index("--file") + 1])
            output.write_bytes(b"custom postgres backup")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("app.backup.shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr("app.backup.subprocess.run", fake_run)
    backup = tmp_path / "opspilot.dump"
    url = "postgresql://opspilot:secret@db:5432/opspilot"

    manifest = create_backup(url, backup)
    verified = verify_backup(backup)

    assert manifest == verified
    assert json.loads(manifest_path(backup).read_text())["database"] == "opspilot"
    with pytest.raises(BackupError, match="目标数据库不一致"):
        restore_backup(
            url,
            backup,
            confirm_database="wrong",
        )

    restored = restore_backup(
        url,
        backup,
        confirm_database="opspilot",
        clean=True,
    )
    assert restored.sha256 == manifest.sha256
    assert commands[-1][0] == "pg_restore"
    assert "--clean" in commands[-1]
    assert commands[-1][commands[-1].index("--dbname") + 1] == "opspilot"


def test_backup_detects_tampering(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(command, **kwargs):
        Path(command[command.index("--file") + 1]).write_bytes(b"valid")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("app.backup.shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr("app.backup.subprocess.run", fake_run)
    backup = tmp_path / "opspilot.dump"
    create_backup("postgresql://user:secret@db/opspilot", backup)
    backup.write_bytes(b"tampered")

    with pytest.raises(BackupError, match="校验失败|大小"):
        verify_backup(backup)


def test_migration_loader_is_ordered_and_checksummed(tmp_path: Path) -> None:
    (tmp_path / "002_second.sql").write_text("SELECT 2;\n", encoding="utf-8")
    (tmp_path / "001_first.sql").write_text("SELECT 1;\n", encoding="utf-8")

    migrations = load_migrations(tmp_path)

    assert [item.version for item in migrations] == ["001", "002"]
    assert all(len(item.checksum) == 64 for item in migrations)


def test_migration_loader_rejects_unsafe_names(tmp_path: Path) -> None:
    (tmp_path / "bad.sql").write_text("SELECT 1;\n", encoding="utf-8")

    with pytest.raises(MigrationError, match="文件名"):
        load_migrations(tmp_path)


def test_local_readiness_and_release_gate(
    settings: Settings,
    tmp_path: Path,
) -> None:
    class ReadyService:
        @staticmethod
        def ensure_ready():
            return {"status": "ready"}

    readiness = check_readiness(
        settings,
        service_factory=ReadyService,
        migrations_dir=tmp_path,
    )
    checks = run_preflight(
        settings,
        service_factory=ReadyService,
        migrations_dir=tmp_path,
        production=True,
        require_backup_tools=False,
    )

    assert readiness.ready is True
    payload = preflight_payload(checks)
    assert payload["passed"] is False
    failed = {item["name"] for item in payload["checks"] if not item["passed"]}
    assert failed == {
        "postgres_backends",
        "authentication",
        "audit",
        "rate_limit",
    }


def test_readiness_reports_index_failure(settings: Settings, tmp_path: Path) -> None:
    class BrokenService:
        @staticmethod
        def ensure_ready():
            raise RuntimeError("internal details must not leak")

    readiness = check_readiness(
        settings,
        service_factory=BrokenService,
        migrations_dir=tmp_path,
    )

    assert readiness.ready is False
    assert readiness.components["knowledge_index"].detail == "知识索引不可用"


def test_release_gate_can_require_metrics_and_traces(
    settings: Settings,
    tmp_path: Path,
) -> None:
    class ReadyService:
        @staticmethod
        def ensure_ready():
            return {"status": "ready"}

    checks = run_preflight(
        settings,
        service_factory=ReadyService,
        migrations_dir=tmp_path,
        production=False,
        require_backup_tools=False,
        require_observability=True,
    )

    failed = {item.name for item in checks if not item.passed}
    assert failed == {"prometheus_metrics", "otel_tracing"}


def test_production_settings_for_preflight() -> None:
    settings = Settings(
        index_backend="postgres",
        persistence_backend="postgres",
        database_url="postgresql://unused",
        auth_enabled=True,
        auth_secret_key="x" * 48,
        audit_enabled=True,
        rate_limit_enabled=True,
    )

    assert settings.auth_enabled is True
