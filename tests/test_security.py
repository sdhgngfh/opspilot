from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api import (
    app,
    get_graph_workflow,
    get_service,
    get_settings,
    get_ticket_store,
    get_ticket_workflow,
    get_user_store,
)
from app.config import Settings
from app.graph import RAGGraphWorkflow, TicketApprovalWorkflow
from app.security import AccessContext, UserStore, hash_password, verify_password
from app.service import RAGService
from app.tools import TicketStore


def _secure_settings(settings: Settings, tmp_path: Path) -> Settings:
    return settings.model_copy(
        update={
            "auth_enabled": True,
            "auth_secret_key": "test-secret-key-that-is-longer-than-32-characters",
            "auth_store_path": tmp_path / "secure-users.sqlite",
        }
    )


def _authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_password_hash_is_salted_and_verifiable() -> None:
    first = hash_password("strong-password")
    second = hash_password("strong-password")

    assert first != second
    assert "strong-password" not in first
    assert verify_password("strong-password", first) is True
    assert verify_password("wrong-password", first) is False


def test_retrieval_applies_role_and_department_acl(service: RAGService) -> None:
    sales = AccessContext(
        user_id="sales",
        username="sales",
        roles=frozenset({"sales"}),
        departments=frozenset({"sales"}),
        scopes=frozenset({"knowledge:read"}),
    )
    support = AccessContext(
        user_id="support",
        username="support",
        roles=frozenset({"support"}),
        departments=frozenset({"it"}),
        scopes=frozenset({"knowledge:read"}),
    )

    sales_hits = service.retrieve("数据库备份恢复演练 RPO RTO", access=sales)
    support_hits = service.retrieve("如何限制本部门销售订单权限？", access=support)

    assert all(
        hit.document.metadata["source"] != "backup_recovery.md"
        for hit in sales_hits
    )
    assert support_hits[0].document.metadata["source"] == "u9c_permissions.md"


def test_authentication_scopes_identity_and_thread_isolation(
    settings: Settings,
    service: RAGService,
    tmp_path: Path,
) -> None:
    secure_settings = _secure_settings(settings, tmp_path)
    store = UserStore(secure_settings.auth_store_path)
    store.create_user(
        username="sales-demo",
        password="sales-password",
        roles=["sales"],
        departments=["sales"],
        scopes=["knowledge:read", "tickets:create", "tickets:read"],
    )
    store.create_user(
        username="support-demo",
        password="support-password",
        roles=["support"],
        departments=["it"],
        scopes=[
            "knowledge:read",
            "knowledge:write",
            "tickets:create",
            "tickets:read",
            "tickets:review",
        ],
    )
    graph = RAGGraphWorkflow(service)
    ticket_store = TicketStore(tmp_path / "secure-tickets.sqlite")
    ticket_workflow = TicketApprovalWorkflow(secure_settings, ticket_store)
    app.dependency_overrides[get_settings] = lambda: secure_settings
    app.dependency_overrides[get_user_store] = lambda: store
    app.dependency_overrides[get_service] = lambda: service
    app.dependency_overrides[get_graph_workflow] = lambda: graph
    app.dependency_overrides[get_ticket_store] = lambda: ticket_store
    app.dependency_overrides[get_ticket_workflow] = lambda: ticket_workflow
    client = TestClient(app)

    try:
        anonymous = client.post(
            "/v1/graph/ask",
            json={"question": "如何配置权限？", "thread_id": "shared"},
        )
        bad_login = client.post(
            "/v1/auth/token",
            data={"username": "sales-demo", "password": "wrong-password"},
        )
        sales_login = client.post(
            "/v1/auth/token",
            data={"username": "sales-demo", "password": "sales-password"},
        )
        support_login = client.post(
            "/v1/auth/token",
            data={"username": "support-demo", "password": "support-password"},
        )
        sales_headers = _authorization(sales_login.json()["access_token"])
        support_headers = _authorization(support_login.json()["access_token"])

        sales_answer = client.post(
            "/v1/graph/ask",
            headers=sales_headers,
            json={"question": "如何限制本部门销售订单权限？", "thread_id": "shared"},
        )
        support_answer = client.post(
            "/v1/graph/ask",
            headers=support_headers,
            json={"question": "如何限制本部门销售订单权限？", "thread_id": "shared"},
        )
        sales_thread = client.get(
            "/v1/graph/threads/shared",
            headers=sales_headers,
        )
        support_thread = client.get(
            "/v1/graph/threads/shared",
            headers=support_headers,
        )

        started = client.post(
            "/v1/tickets/workflows",
            headers=sales_headers,
            json={
                "request_text": "订单审核失败，请创建排查工单。",
                "requester": "spoofed-user",
                "thread_id": "secure-ticket",
            },
        )
        forbidden_review = client.post(
            "/v1/tickets/workflows/secure-ticket/review",
            headers=sales_headers,
            json={"action": "approve", "reviewer": "spoofed-reviewer"},
        )
        reviewed = client.post(
            "/v1/tickets/workflows/secure-ticket/review",
            headers=support_headers,
            json={"action": "approve", "reviewer": "spoofed-reviewer"},
        )

        assert anonymous.status_code == 401
        assert bad_login.status_code == 401
        assert sales_login.status_code == 200
        assert support_login.status_code == 200
        assert all(
            citation["source"] != "u9c_permissions.md"
            for citation in sales_answer.json()["citations"]
        )
        assert support_answer.json()["citations"][0]["source"] == "u9c_permissions.md"
        assert len(sales_thread.json()["history"]) == 1
        assert len(support_thread.json()["history"]) == 1
        assert started.json()["tool_call"]["arguments"]["requester"] == "sales-demo"
        assert forbidden_review.status_code == 403
        assert reviewed.json()["ticket"]["reviewer"] == "support-demo"
    finally:
        app.dependency_overrides.clear()
