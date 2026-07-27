from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class Citation(BaseModel):
    rank: int
    source: str
    title: str
    chunk_id: str
    score: float
    excerpt: str


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=20)


class AskResponse(BaseModel):
    question: str
    answer: str
    grounded: bool
    citations: list[Citation]
    latency_ms: float


class GraphAskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    thread_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1, max_length=200)
    top_k: int | None = Field(default=None, ge=1, le=20)
    max_rewrites: int | None = Field(default=None, ge=0, le=5)


class RetrievalAttempt(BaseModel):
    attempt: int
    query: str
    top_score: float
    evidence_score: float
    sufficient: bool
    reason: str


class ConversationTurn(BaseModel):
    question: str
    retrieval_query: str
    answer: str
    grounded: bool


class GraphAskResponse(AskResponse):
    thread_id: str
    retrieval_query: str
    rewrite_count: int
    evidence_score: float
    evidence_reason: str
    execution_path: list[str]
    attempts: list[RetrievalAttempt]


class ThreadStateResponse(BaseModel):
    thread_id: str
    history: list[ConversationTurn]
    last_question: str | None = None
    checkpoint_created_at: str | None = None


class IngestResponse(BaseModel):
    documents: int
    chunks: int
    rebuilt: bool
    corpus_fingerprint: str
    embedding_signature: str


class SystemInfoResponse(BaseModel):
    version: str
    rag_mode: str
    embedding_provider: str
    retrieval_strategy: str
    reranker_provider: str


class EvaluationCase(BaseModel):
    id: str
    question: str
    answerable: bool
    question_type: Literal["error_code", "out_of_scope", "policy", "procedure", "troubleshooting"]
    difficulty: Literal["easy", "medium", "hard"]
    expected_sources: list[str] = Field(default_factory=list)
    answer_keywords: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_labels(self) -> EvaluationCase:
        if self.answerable and not self.expected_sources:
            raise ValueError("可回答样本必须标注 expected_sources")
        if not self.answerable and (self.expected_sources or self.answer_keywords):
            raise ValueError("不可回答样本不得声明来源或答案关键词")
        return self


class CaseResult(BaseModel):
    id: str
    question: str
    answerable: bool
    question_type: str
    difficulty: str
    grounded: bool
    retrieved_sources: list[str]
    reciprocal_rank: float
    recall_at_k: float
    keyword_recall: float | None
    latency_ms: float


class EvaluationSlice(BaseModel):
    dimension: str
    value: str
    cases: int
    hit_rate_at_k: float
    mrr: float
    answer_keyword_recall: float
    abstention_accuracy: float


class EvaluationSummary(BaseModel):
    retrieval_strategy: str
    cases: int
    k: int
    hit_rate_at_k: float
    recall_at_k: float
    mrr: float
    answer_keyword_recall: float
    abstention_accuracy: float
    average_latency_ms: float
    breakdowns: dict[str, list[EvaluationSlice]]
    results: list[CaseResult]


class GraphComparisonCaseResult(BaseModel):
    id: str
    question: str
    answerable: bool
    base_grounded: bool
    graph_grounded: bool
    base_source_hit: bool
    graph_source_hit: bool
    base_keyword_recall: float | None
    graph_keyword_recall: float | None
    rewrite_count: int
    attempts: int
    recovered_after_rewrite: bool
    base_latency_ms: float
    graph_latency_ms: float


class GraphEvaluationSummary(BaseModel):
    cases: int
    base_decision_accuracy: float
    graph_decision_accuracy: float
    base_source_hit_rate: float
    graph_source_hit_rate: float
    base_answer_keyword_recall: float
    graph_answer_keyword_recall: float
    rewrite_rate: float
    retry_recovery_rate: float
    average_attempts: float
    base_average_latency_ms: float
    graph_average_latency_ms: float
    results: list[GraphComparisonCaseResult]
