from __future__ import annotations

import json
import sys

import httpx

from scripts import fault_drill


class _TransientClient:
    def __init__(self) -> None:
        self.request_count = 0

    def __enter__(self) -> _TransientClient:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def get(self, path: str) -> httpx.Response:
        self.request_count += 1
        if self.request_count == 1:
            raise httpx.ReadError("connection reset")
        payload = {"status": "ok"} if path == "/health/live" else {"status": "ready"}
        return httpx.Response(200, json=payload)


class _InvalidJsonThenDegradedClient:
    def __init__(self) -> None:
        self.request_count = 0

    def __enter__(self) -> _InvalidJsonThenDegradedClient:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def get(self, path: str) -> httpx.Response:
        self.request_count += 1
        if self.request_count == 2:
            return httpx.Response(500, text="Internal Server Error")
        if path == "/health/live":
            return httpx.Response(200, json={"status": "alive"})
        return httpx.Response(503, json={"status": "not_ready"})


def test_fault_drill_retries_transient_connection_errors(
    monkeypatch,
    capsys,
) -> None:
    client = _TransientClient()
    monkeypatch.setattr(fault_drill.httpx, "Client", lambda **_kwargs: client)
    monkeypatch.setattr(fault_drill.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["fault_drill.py", "--expect", "ready", "--attempts", "2"],
    )

    fault_drill.main()

    result = json.loads(capsys.readouterr().out)
    assert result["attempt"] == 2
    assert result["liveness_status"] == 200
    assert result["readiness_status"] == 200


def test_fault_drill_retries_transient_non_json_responses(
    monkeypatch,
    capsys,
) -> None:
    client = _InvalidJsonThenDegradedClient()
    monkeypatch.setattr(fault_drill.httpx, "Client", lambda **_kwargs: client)
    monkeypatch.setattr(fault_drill.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["fault_drill.py", "--expect", "degraded", "--attempts", "2"],
    )

    fault_drill.main()

    result = json.loads(capsys.readouterr().out)
    assert result["attempt"] == 2
    assert result["liveness_status"] == 200
    assert result["readiness_status"] == 503
