from __future__ import annotations

import subprocess
import sys


def test_fastapi_testclient_uses_supported_http_client() -> None:
    script = """
import warnings
from starlette.exceptions import StarletteDeprecationWarning

warnings.simplefilter("error", StarletteDeprecationWarning)
from fastapi.testclient import TestClient

assert TestClient is not None
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
