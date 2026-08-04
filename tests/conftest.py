from __future__ import annotations

from pathlib import Path

import pytest

from app.config import PROJECT_ROOT, Settings
from app.graph import RAGGraphWorkflow
from app.service import RAGService


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        rag_mode="local",
        embedding_provider="local",
        knowledge_dir=PROJECT_ROOT / "data" / "knowledge",
        index_path=tmp_path / "vector_store.json",
        checkpoint_path=tmp_path / "checkpoints.sqlite",
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
