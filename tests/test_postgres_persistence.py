from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest

from app.audit import PostgresAuditStore, new_audit_event
from app.config import PROJECT_ROOT, Settings
from app.graph import RAGGraphWorkflow, TicketApprovalWorkflow
from app.migrations import PostgresMigrator
from app.models import StartTicketWorkflowRequest, TicketReviewRequest
from app.postgres_stores import PostgresTicketStore, PostgresUserStore
from app.rate_limit import PostgresRateLimiter
from app.service import RAGService


@pytest.mark.integration
def test_postgres_state_survives_workflow_recreation(tmp_path: Path) -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    unique = uuid4().hex
    migration_states = PostgresMigrator(
        database_url,
        PROJECT_ROOT / "migrations",
    ).apply()
    assert all(item.status == "applied" for item in migration_states)
    settings = Settings(
        rag_mode="local",
        embedding_provider="local",
        persistence_backend="postgres",
        database_url=database_url,
        knowledge_dir=PROJECT_ROOT / "data" / "knowledge",
        index_path=tmp_path / "vector_store.json",
        checkpoint_path=tmp_path / "unused-checkpoints.sqlite",
        ticket_checkpoint_path=tmp_path / "unused-ticket-checkpoints.sqlite",
    )

    users = PostgresUserStore(database_url)
    identity = users.create_user(
        username=f"user-{unique}",
        password="postgres-password",
        roles=["support"],
        departments=["it"],
        scopes=["knowledge:read", "tickets:create", "tickets:read"],
        external_subject=f"https://id.example.com|{unique}",
    )
    assert users.authenticate(identity.username, "postgres-password") == identity
    assert users.get_by_external_subject(
        f"https://id.example.com|{unique}"
    ) == identity

    service = RAGService(settings)
    service.ensure_ready()
    thread_id = f"rag-{unique}"
    first = RAGGraphWorkflow(service)
    first.ask(
        question="AUTH-403-DATA 表示什么？",
        thread_id=thread_id,
        access=identity,
    )
    recreated = RAGGraphWorkflow(service)
    assert recreated.get_thread(thread_id) is not None

    tickets = PostgresTicketStore(database_url)
    ticket_thread = f"ticket-{unique}"
    approval = TicketApprovalWorkflow(settings, tickets)
    approval.start(
        StartTicketWorkflowRequest(
            request_text="生产权限异常，请创建排查工单。",
            requester=identity.username,
            thread_id=ticket_thread,
        )
    )
    recreated_approval = TicketApprovalWorkflow(settings, tickets)
    submitted = recreated_approval.review(
        ticket_thread,
        TicketReviewRequest(action="approve", reviewer="ops-lead"),
    )
    assert submitted.ticket is not None
    assert tickets.get_by_workflow(ticket_thread) == submitted.ticket

    audit = PostgresAuditStore(database_url)
    audit.record(
        new_audit_event(
            request_id=unique,
            actor_id=identity.user_id,
            actor_username=identity.username,
            method="POST",
            path="/v1/graph/ask",
            status_code=200,
            latency_ms=3.0,
        )
    )
    assert any(item.request_id == unique for item in audit.list_recent(limit=20))

    limiter = PostgresRateLimiter(database_url, limit=1, window_seconds=60)
    assert limiter.check(unique).allowed is True
    assert limiter.check(unique).allowed is False
