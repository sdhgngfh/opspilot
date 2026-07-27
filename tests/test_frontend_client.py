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
            lambda request: httpx.Response(409, json={"detail": "已经审批"})
        ),
    )

    with pytest.raises(OpsPilotAPIError, match="已经审批"):
        client.review_ticket(
            "ticket-1",
            action="approve",
            reviewer="ops-lead",
        )


def test_frontend_client_attaches_bearer_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer secure-token"
        return httpx.Response(200, json={"username": "alice"})

    client = OpsPilotClient(
        "http://test",
        access_token="secure-token",
        transport=httpx.MockTransport(handler),
    )

    assert client.me()["username"] == "alice"
