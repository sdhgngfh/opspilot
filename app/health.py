from __future__ import annotations

from collections.abc import Callable
from typing import Any


class Readiness:
    def __init__(self, ready: bool):
        self._ready = ready

    @property
    def ready(self) -> bool:
        return self._ready

    def model_dump(self) -> dict[str, Any]:
        return {"status": "ready" if self._ready else "not_ready", "components": {}}


def check_readiness(*, service_factory: Callable[[], Any]) -> Readiness:
    try:
        service_factory().ensure_ready()
    except Exception:
        return Readiness(False)
    return Readiness(True)
