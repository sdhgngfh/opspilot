from __future__ import annotations

from fastapi.testclient import TestClient

import app.api as api_module
from app.api import app, get_graph_workflow, get_service
from app.graph import RAGGraphWorkflow
from app.service import RAGService


def test_health_and_ask(service: RAGService, monkeypatch) -> None:
    app.dependency_overrides[get_service] = lambda: service
    monkeypatch.setattr(api_module, "get_service", lambda: service)
    client = TestClient(app)

    health = client.get("/health")
    live = client.get("/health/live")
    ready = client.get("/health/ready")
    answer = client.post("/v1/ask", json={"question": "销售订单审核失败检查什么？"})

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert live.status_code == 200
    assert live.json() == {"status": "alive"}
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["components"]["knowledge_index"]["status"] == "ok"
    assert answer.status_code == 200
    assert answer.json()["grounded"] is True
    assert answer.json()["citations"]
    app.dependency_overrides.clear()


def test_system_info_exposes_safe_runtime_configuration() -> None:
    client = TestClient(app)

    response = client.get("/v1/system/info")

    assert response.status_code == 200
    assert response.json()["version"] == "0.11.0"
    assert response.json()["index_backend"] == "local"
    assert response.json()["persistence_backend"] == "local"
    assert response.json()["auth_enabled"] is False
    assert response.json()["auth_provider"] == "local"
    assert response.json()["reranker_provider"] == "local"
    assert response.json()["tracing_enabled"] is False


def test_graph_api_and_thread_state(
    service: RAGService,
    workflow: RAGGraphWorkflow,
) -> None:
    app.dependency_overrides[get_service] = lambda: service
    app.dependency_overrides[get_graph_workflow] = lambda: workflow
    client = TestClient(app)

    answer = client.post(
        "/v1/graph/ask",
        json={
            "question": "AUTH-403-DATA 表示什么？",
            "thread_id": "api-thread",
        },
    )
    thread = client.get("/v1/graph/threads/api-thread")

    assert answer.status_code == 200
    assert answer.json()["grounded"] is True
    assert answer.json()["execution_path"] == [
        "prepare_query",
        "retrieve",
        "grade_evidence",
        "generate_answer",
        "finalize",
    ]
    assert thread.status_code == 200
    assert len(thread.json()["history"]) == 1
    app.dependency_overrides.clear()


def test_unknown_graph_thread_returns_404(workflow: RAGGraphWorkflow) -> None:
    app.dependency_overrides[get_graph_workflow] = lambda: workflow
    client = TestClient(app)

    response = client.get("/v1/graph/threads/missing")

    assert response.status_code == 404
    app.dependency_overrides.clear()
