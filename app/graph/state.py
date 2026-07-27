from __future__ import annotations

from typing import TypedDict

from langchain_core.documents import Document

from app.index import RetrievalHit


class SerializedHit(TypedDict):
    page_content: str
    metadata: dict[str, object]
    score: float
    vector_score: float
    bm25_score: float
    rrf_score: float
    lexical_score: float
    rerank_score: float
    model_rerank_score: float


class RAGGraphState(TypedDict, total=False):
    question: str
    original_question: str
    retrieval_query: str
    top_k: int
    max_rewrites: int
    rewrite_count: int
    raw_hits: list[SerializedHit]
    selected_hits: list[SerializedHit]
    evidence_score: float
    evidence_reason: str
    evidence_sufficient: bool
    answer: str
    grounded: bool
    citations: list[dict[str, object]]
    execution_path: list[str]
    attempts: list[dict[str, object]]
    history: list[dict[str, object]]
    access_context: dict[str, object]


def serialize_hit(hit: RetrievalHit) -> SerializedHit:
    return SerializedHit(
        page_content=hit.document.page_content,
        metadata=dict(hit.document.metadata),
        score=hit.score,
        vector_score=hit.vector_score,
        bm25_score=hit.bm25_score,
        rrf_score=hit.rrf_score,
        lexical_score=hit.lexical_score,
        rerank_score=hit.rerank_score,
        model_rerank_score=hit.model_rerank_score,
    )


def deserialize_hit(data: SerializedHit) -> RetrievalHit:
    return RetrievalHit(
        document=Document(
            page_content=data["page_content"],
            metadata=data["metadata"],
        ),
        score=float(data["score"]),
        vector_score=float(data["vector_score"]),
        bm25_score=float(data["bm25_score"]),
        rrf_score=float(data["rrf_score"]),
        lexical_score=float(data["lexical_score"]),
        rerank_score=float(data["rerank_score"]),
        model_rerank_score=float(data.get("model_rerank_score", 0.0)),
    )
