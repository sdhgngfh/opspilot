from __future__ import annotations

from fastapi.testclient import TestClient

import app.api as api_module
from app.api import (
    app,
    get_graph_workflow,
    get_service,
    get_settings,
    get_ticket_store,
    get_ticket_workflow,
)
from app.config import Settings
from app.graph import RAGGraphWorkflow, TicketApprovalWorkflow
from app.service import RAGService
from app.tools import TicketStore


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


def test_health_probes_bypass_database_backed_security_controls(
    settings: Settings,
    service: RAGService,
    monkeypatch,
) -> None:
    protected_settings = settings.model_copy(
        update={
            "rate_limit_enabled": True,
            "audit_enabled": True,
        }
    )

    def fail_if_called():
        raise AssertionError("health probes must not use database-backed controls")

    app.dependency_overrides[get_settings] = lambda: protected_settings
    app.dependency_overrides[get_service] = lambda: service
    monkeypatch.setattr(api_module, "get_settings", lambda: protected_settings)
    monkeypatch.setattr(api_module, "get_service", lambda: service)
    monkeypatch.setattr(api_module, "get_rate_limiter", fail_if_called)
    monkeypatch.setattr(api_module, "get_audit_store", fail_if_called)
    client = TestClient(app)

    try:
        live = client.get("/health/live")
        ready = client.get("/health/ready")

        assert live.status_code == 200
        assert live.json() == {"status": "alive"}
        assert ready.status_code == 200
        assert ready.json()["status"] == "ready"
    finally:
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
    assert response.json()["audit_enabled"] is False
    assert response.json()["rate_limit_enabled"] is False
    assert response.json()["reranker_provider"] == "local"
    assert response.json()["reranker_model"] is None
    assert response.json()["tracing_enabled"] is False
    assert response.json()["metrics_enabled"] is False
    assert response.json()["otel_tracing_enabled"] is False
    assert response.json()["otel_service_name"] is None
    assert response.json()["deployment_environment"] == "local"


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


def test_managed_deployment_disables_in_process_knowledge_mutations(
    settings: Settings,
) -> None:
    managed = settings.model_copy(update={"knowledge_mutations_enabled": False})
    app.dependency_overrides[get_settings] = lambda: managed
    client = TestClient(app)
    try:
        reindex = client.post("/v1/documents/reindex")
        upload = client.post(
            "/v1/documents/upload",
            files={"file": ("new.md", b"# new", "text/markdown")},
        )
    finally:
        app.dependency_overrides.clear()

    assert reindex.status_code == 503
    assert upload.status_code == 503
    assert reindex.json()["detail"] == "当前部署由受控索引任务管理知识变更"


def test_ticket_approval_api(
    ticket_workflow: TicketApprovalWorkflow,
    ticket_store: TicketStore,
) -> None:
    app.dependency_overrides[get_ticket_workflow] = lambda: ticket_workflow
    app.dependency_overrides[get_ticket_store] = lambda: ticket_store
    client = TestClient(app)

    started = client.post(
        "/v1/tickets/workflows",
        json={
            "request_text": "销售人员可以看到其他部门订单，请创建权限修复工单。",
            "requester": "alice",
            "thread_id": "api-ticket",
        },
    )
    before_review = client.get("/v1/tickets/workflows/api-ticket")
    assert started.status_code == 200
    assert started.json()["status"] == "awaiting_approval"
    assert before_review.json()["approval_request"]["tool_call"]["name"] == "submit_ticket"
    assert ticket_store.count() == 0

    reviewed = client.post(
        "/v1/tickets/workflows/api-ticket/review",
        json={"action": "approve", "reviewer": "ops-lead"},
    )
    ticket_id = reviewed.json()["ticket"]["ticket_id"]
    ticket = client.get(f"/v1/tickets/{ticket_id}")

    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "submitted"
    assert ticket.status_code == 200
    assert ticket.json()["workflow_id"] == "api-ticket"
    app.dependency_overrides.clear()


def test_ticket_review_validation_and_conflict(
    ticket_workflow: TicketApprovalWorkflow,
) -> None:
    app.dependency_overrides[get_ticket_workflow] = lambda: ticket_workflow
    client = TestClient(app)

    missing_changes = client.post(
        "/v1/tickets/workflows/missing/review",
        json={"action": "edit", "reviewer": "ops-lead"},
    )
    missing_workflow = client.post(
        "/v1/tickets/workflows/missing/review",
        json={"action": "approve", "reviewer": "ops-lead"},
    )

    assert missing_changes.status_code == 422
    assert missing_workflow.status_code == 404
    app.dependency_overrides.clear()
