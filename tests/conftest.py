from __future__ import annotations

from pathlib import Path

import pytest

from app.config import PROJECT_ROOT, Settings
from app.graph import RAGGraphWorkflow, TicketApprovalWorkflow
from app.service import RAGService
from app.tools import TicketStore


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        rag_mode="local",
        embedding_provider="local",
        knowledge_dir=PROJECT_ROOT / "data" / "knowledge",
        index_path=tmp_path / "vector_store.json",
        checkpoint_path=tmp_path / "checkpoints.sqlite",
        ticket_checkpoint_path=tmp_path / "ticket_checkpoints.sqlite",
        ticket_store_path=tmp_path / "tickets.sqlite",
        evaluation_dataset=PROJECT_ROOT / "data" / "evaluation" / "dataset.jsonl",
        retrieval_strategy="hybrid_rerank",
        top_k=4,
        candidate_k=12,
        min_relevance_score=0.18,
        min_bm25_score=0.8,
        min_lexical_coverage=0.12,
        vector_weight=0.55,
        bm25_weight=0.45,
        rrf_k=60,
        chunk_size=600,
        chunk_overlap=100,
    )


@pytest.fixture
def service(settings: Settings) -> RAGService:
    instance = RAGService(settings)
    instance.ensure_ready()
    return instance


@pytest.fixture
def workflow(service: RAGService) -> RAGGraphWorkflow:
    return RAGGraphWorkflow(service)


@pytest.fixture
def ticket_store(settings: Settings) -> TicketStore:
    return TicketStore(settings.ticket_store_path)


@pytest.fixture
def ticket_workflow(
    settings: Settings,
    ticket_store: TicketStore,
) -> TicketApprovalWorkflow:
    return TicketApprovalWorkflow(settings, ticket_store)
