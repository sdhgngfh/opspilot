from __future__ import annotations

from typing import Any

import httpx


class OpsPilotAPIError(RuntimeError):
    pass


class OpsPilotClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            transport=transport,
            trust_env=False,
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self._client.request(method, path, **kwargs)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            try:
                detail = exc.response.json().get("detail", exc.response.text)
            except ValueError:
                detail = exc.response.text
            raise OpsPilotAPIError(f"API 返回 {exc.response.status_code}：{detail}") from exc
        except httpx.HTTPError as exc:
            raise OpsPilotAPIError(f"无法连接 OpsPilot API：{exc}") from exc
        return response.json()

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def system_info(self) -> dict[str, Any]:
        return self._request("GET", "/v1/system/info")

    def ask(self, question: str, thread_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/graph/ask",
            json={"question": question, "thread_id": thread_id},
        )
