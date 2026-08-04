from __future__ import annotations

import httpx
import pytest

from frontend.client import OpsPilotAPIError, OpsPilotClient


def test_frontend_client_sends_graph_thread_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/graph/ask"
        assert request.method == "POST"
        assert b'"thread_id":"demo-thread"' in request.content
        return httpx.Response(
            200,
            json={
                "answer": "证据回答",
                "citations": [],
                "execution_path": ["prepare_query", "retrieve"],
            },
        )

    client = OpsPilotClient(
        "http://test",
        transport=httpx.MockTransport(handler),
    )

    response = client.ask("如何配置权限？", "demo-thread")

    assert response["answer"] == "证据回答"


def test_frontend_client_surfaces_api_detail() -> None:
    client = OpsPilotClient(
        "http://test",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(409, json={"detail": "服务不可用"})
        ),
    )

    with pytest.raises(OpsPilotAPIError, match="服务不可用"):
        client.system_info()


def test_frontend_client_health_and_system_info() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path == "/v1/system/info":
            return httpx.Response(200, json={"rag_mode": "local"})
        return httpx.Response(404, json={"detail": "not found"})

    client = OpsPilotClient(
        "http://test",
        transport=httpx.MockTransport(handler),
    )

    assert client.health()["status"] == "ok"
    assert client.system_info()["rag_mode"] == "local"
