from __future__ import annotations

from app.config import PROJECT_ROOT


def test_docker_base_matches_postgresql_repository_distribution() -> None:
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM python:3.12-slim-bookworm" in dockerfile
    assert "bookworm-pgdg" in dockerfile


def test_docker_scripts_import_application_from_workdir() -> None:
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "PYTHONPATH=/app" in dockerfile
