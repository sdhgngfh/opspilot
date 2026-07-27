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
        access_token: str | None = None,
    ) -> None:
        self._access_token = access_token
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            transport=transport,
            trust_env=False,
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        headers = dict(kwargs.pop("headers", {}))
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        try:
            response = self._client.request(method, path, headers=headers, **kwargs)
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

    def login(self, username: str, password: str) -> dict[str, Any]:
        response = self._request(
            "POST",
            "/v1/auth/token",
            data={"username": username, "password": password},
        )
        self._access_token = str(response["access_token"])
        return response

    def set_access_token(self, access_token: str | None) -> None:
        self._access_token = access_token

    def me(self) -> dict[str, Any]:
        return self._request("GET", "/v1/auth/me")

    def ask(self, question: str, thread_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/graph/ask",
            json={"question": question, "thread_id": thread_id},
        )

    def start_ticket(
        self,
        request_text: str,
        requester: str,
        thread_id: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/tickets/workflows",
            json={
                "request_text": request_text,
                "requester": requester,
                "thread_id": thread_id,
            },
        )

    def review_ticket(
        self,
        thread_id: str,
        *,
        action: str,
        reviewer: str,
        changes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"action": action, "reviewer": reviewer}
        if changes is not None:
            payload["changes"] = changes
        return self._request(
            "POST",
            f"/v1/tickets/workflows/{thread_id}/review",
            json=payload,
        )

    def upload_document(
        self,
        filename: str,
        content: bytes,
        content_type: str,
        *,
        replace: bool,
        allowed_roles: list[str] | None = None,
        allowed_departments: list[str] | None = None,
        classification: str = "internal",
    ) -> dict[str, Any]:
        params: list[tuple[str, str]] = [
            ("replace", str(replace).lower()),
            ("classification", classification),
        ]
        params.extend(("allowed_roles", item) for item in allowed_roles or [])
        params.extend(
            ("allowed_departments", item)
            for item in allowed_departments or []
        )
        return self._request(
            "POST",
            "/v1/documents/upload",
            params=params,
            files={"file": (filename, content, content_type)},
        )
