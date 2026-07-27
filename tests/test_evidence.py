from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.evidence import (
    EvidenceCheck,
    build_evidence,
    git_metadata,
    redact_secrets,
    render_markdown,
    run_check,
)


def test_redact_secrets_removes_database_password_and_tokens() -> None:
    value = (
        "postgresql://alice:super-secret@db:5432/app "
        "Authorization: Bearer abc.def.ghi API_KEY=secret-value"
    )

    redacted = redact_secrets(value)

    assert "super-secret" not in redacted
    assert "abc.def.ghi" not in redacted
    assert "secret-value" not in redacted
    assert redacted.count("***") == 3


def test_run_check_records_artifact_hash_and_redacts_output(tmp_path: Path) -> None:
    artifact = tmp_path / "report.json"
    artifact.write_text('{"status":"ok"}\n', encoding="utf-8")

    check = run_check(
        "sample",
        [
            "python",
            "-c",
            "print('postgresql://user:password@db/app')",
        ],
        project_root=tmp_path,
        artifact_paths=(artifact,),
    )

    assert check.status == "passed"
    assert "password" not in check.output_tail
    assert check.artifacts[0].path == "report.json"
    assert len(check.artifacts[0].sha256) == 64


def test_evidence_keeps_skipped_separate_from_passed(tmp_path: Path) -> None:
    checks = [
        EvidenceCheck("unit", "passed", "ok"),
        EvidenceCheck("postgres", "skipped", "not configured"),
    ]

    evidence = build_evidence(
        project_root=tmp_path,
        checks=checks,
        started_at=datetime.now(UTC),
    )
    markdown = render_markdown(evidence)

    assert evidence["status"] == "partial"
    assert evidence["summary"] == {"passed": 1, "failed": 0, "skipped": 1}
    assert "| postgres | skipped |" in markdown
    assert "跳过项不计作通过" in markdown


def test_failed_check_fails_evidence(tmp_path: Path) -> None:
    evidence = build_evidence(
        project_root=tmp_path,
        checks=[EvidenceCheck("lint", "failed", "exit_code=1")],
        started_at=datetime.now(UTC),
    )

    assert evidence["status"] == "failed"


def test_git_metadata_reports_absent_repository(tmp_path: Path) -> None:
    assert git_metadata(tmp_path) == {
        "available": False,
        "commit": None,
        "tag": None,
        "dirty": None,
    }


def test_git_metadata_reports_unavailable_git_binary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr("app.evidence.shutil.which", lambda _: None)

    assert git_metadata(tmp_path) == {
        "available": False,
        "commit": None,
        "tag": None,
        "dirty": None,
    }
