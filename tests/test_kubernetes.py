from __future__ import annotations

import subprocess
from pathlib import Path

from app.config import PROJECT_ROOT
from app.kubernetes import (
    checks_payload,
    run_helm_checks,
    validate_chart,
    validate_expand_only_migrations,
)

CHART = PROJECT_ROOT / "deploy" / "helm" / "opspilot-rag"


def test_helm_chart_passes_static_release_gate() -> None:
    checks = validate_chart(CHART, migrations_dir=PROJECT_ROOT / "migrations")
    payload = checks_payload(checks)

    assert payload["passed"] is True
    assert {item.name for item in checks} >= {
        "migration_hook",
        "rolling_update",
        "autoscaling",
        "disruption_budget",
        "network_policy",
        "no_embedded_secret",
        "expand_only_migrations",
    }


def test_release_gate_reports_missing_chart_files(tmp_path: Path) -> None:
    checks = validate_chart(tmp_path)

    assert checks == [
        checks[0]
    ]
    assert checks[0].name == "required_files"
    assert checks[0].passed is False
    assert "Chart.yaml" in checks[0].detail


def test_helm_checks_execute_lint_and_template(
    monkeypatch,
) -> None:
    commands: list[list[str]] = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("app.kubernetes.shutil.which", lambda name: "/usr/bin/helm")
    monkeypatch.setattr("app.kubernetes.subprocess.run", fake_run)

    checks = run_helm_checks(CHART)

    assert all(check.passed for check in checks)
    assert [command[1] for command in commands] == ["lint", "template"]
    assert all("secrets.existingSecret=opspilot-secrets" in command for command in commands)


def test_expand_only_gate_rejects_destructive_migration(tmp_path: Path) -> None:
    (tmp_path / "003_drop.sql").write_text(
        "ALTER TABLE app_users DROP COLUMN username;\n",
        encoding="utf-8",
    )

    result = validate_expand_only_migrations(tmp_path)

    assert result.passed is False
    assert "003_drop.sql" in result.detail
